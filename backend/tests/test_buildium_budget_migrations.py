from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property
from app.models.property_budget import PropertyBudgetLine
from app.models.user import Organization
from app.routers import buildium_budget_migrations as api
from app.routers import buildium_migrations as buildium_api
from app.schemas.buildium_budget_migration import (
    BuildiumBudgetCommitIn,
    BuildiumBudgetDryRunIn,
    BuildiumBudgetResolutionIn,
)
from app.schemas.buildium_migration import BuildiumMigrationRunCreateIn


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_user(db, role=PlatformUserRole.PLATFORM_ADMIN):
    row = PlatformUser(
        email=f"{role.value}-{db.query(PlatformUser).count()}@example.com",
        hashed_password=hash_password("buildium-budget-test-password"),
        first_name="Platform",
        last_name="Budget",
        role=role,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db, name="Buildium Budget Org"):
    row = Organization(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    admin = _platform_user(db)
    org = _org(db)
    run = buildium_api.create_run(
        BuildiumMigrationRunCreateIn(
            organization_id=org.id,
            source_account_ref="buildium-budget-source",
        ),
        db=db,
        current_user=admin,
    )
    prop = Property(
        organization_id=org.id,
        name="Budget Property",
        address_line1="100 Budget Way",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        is_active=True,
    )
    gl = GLAccount(
        organization_id=org.id,
        gl_number="4100",
        name="Rent Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add_all([prop, gl])
    db.flush()
    db.add_all([
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="PROPERTIES",
            source_id="501",
            target_entity="PROPERTY",
            target_id=prop.id,
            source_fingerprint="1" * 64,
            created_by_platform_user_id=admin.id,
        ),
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="GL_ACCOUNTS",
            source_id="601",
            target_entity="GL_ACCOUNT",
            target_id=gl.id,
            source_fingerprint="2" * 64,
            created_by_platform_user_id=admin.id,
        ),
    ])
    lines = []
    for month in range(1, 13):
        line = PropertyBudgetLine(
            organization_id=org.id,
            property_id=prop.id,
            gl_account_id=gl.id,
            calendar_year=2026,
            month=month,
            amount=Decimal("100.00"),
        )
        db.add(line)
        lines.append(line)
    db.commit()
    return admin, org, run, prop, gl, lines


def _record(**changes):
    monthly = {
        name: 100 for name in (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        )
    }
    record = {
        "Id": 701,
        "Name": "2026 Operating Budget",
        "StartDate": "2026-01-01",
        "EndDate": "2026-12-31",
        "Property": {"Id": 501, "Type": "Rental", "Href": "/rentals/501"},
        "Details": [{
            "GLAccountId": 601,
            "GLAccountSubType": "Income",
            "TotalAmount": 1200,
            "MonthlyAmounts": monthly,
        }],
    }
    record.update(changes)
    return record


def _resolutions(lines):
    return [
        BuildiumBudgetResolutionIn(
            source_id=f"701:601:2026:{month}",
            action="MATCH_EXISTING",
            target_property_budget_line_id=line.id,
        )
        for month, line in enumerate(lines, start=1)
    ]


def test_buildium_budget_dry_run_requires_review_and_never_mutates_targets():
    db, engine = _session()
    try:
        admin, org, run, prop, gl, lines = _fixture(db)
        before = {
            "budgets": [(line.id, str(line.amount)) for line in lines],
            "gl": db.query(GLTransaction).count(),
            "mappings": db.query(PlatformMigrationItem).count(),
        }
        result = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert result.provider == "BUILDIUM"
        assert result.total == 12
        assert result.reviewable == 12
        assert result.invalid == 0
        assert result.skipped_review == 0
        assert all(row.reason and "Explicit MATCH_EXISTING" in row.reason for row in result.rows)
        assert all(row.mapped["target_property_id"] == prop.id for row in result.rows)
        assert all(row.mapped["target_gl_account_id"] == gl.id for row in result.rows)
        assert all("Possible exact existing Property Budget Line match" in row.warnings[-1] for row in result.rows)

        after = {
            "budgets": [(line.id, str(db.get(PropertyBudgetLine, line.id).amount)) for line in lines],
            "gl": db.query(GLTransaction).count(),
            "mappings": db.query(PlatformMigrationItem).count(),
        }
        assert after == before
        assert db.query(AuditLog).filter(
            AuditLog.action == "buildium_budgets_dry_run"
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_budget_explicit_match_commit_is_mapping_only_and_replay_safe():
    db, engine = _session()
    try:
        admin, org, run, prop, gl, lines = _fixture(db)
        resolutions = _resolutions(lines)
        dry = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[_record()], resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        before_budget = [(line.id, str(line.amount), line.updated_at) for line in lines]
        before_gl = db.query(GLTransaction).count()

        committed = api.commit_buildium_budgets(
            run.id,
            BuildiumBudgetCommitIn(
                records=[_record()],
                resolutions=resolutions,
                fingerprint=dry.fingerprint,
            ),
            db=db,
            current_user=admin,
        )
        assert committed.replayed is False
        assert committed.matched_existing == 12
        assert len(committed.rows) == 12
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == "BUDGET_LINES",
            PlatformMigrationItem.target_entity == "PROPERTY_BUDGET_LINE",
        ).count() == 12
        assert [(line.id, str(db.get(PropertyBudgetLine, line.id).amount), db.get(PropertyBudgetLine, line.id).updated_at) for line in lines] == before_budget
        assert db.query(GLTransaction).count() == before_gl

        replay_dry = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[_record()], resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        assert replay_dry.fingerprint == dry.fingerprint
        replay = api.commit_buildium_budgets(
            run.id,
            BuildiumBudgetCommitIn(
                records=[_record()],
                resolutions=resolutions,
                fingerprint=replay_dry.fingerprint,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.matched_existing == 0
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "BUDGET_LINES",
        ).count() == 12
        assert db.query(AuditLog).filter(
            AuditLog.action == "buildium_budgets_reconciled"
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_budget_rejects_fiscal_period_mismatch_and_stale_target():
    db, engine = _session()
    try:
        admin, org, run, prop, gl, lines = _fixture(db)
        fiscal = _record(StartDate="2026-07-01", EndDate="2027-06-30")
        invalid = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[fiscal]),
            db=db,
            current_user=admin,
        )
        assert invalid.invalid == 1
        assert invalid.total == 1
        assert "calendar-year" in invalid.rows[0].reason

        resolutions = _resolutions(lines)
        dry = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[_record()], resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        lines[0].amount = Decimal("101.00")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_budgets(
                run.id,
                BuildiumBudgetCommitIn(
                    records=[_record()],
                    resolutions=resolutions,
                    fingerprint=dry.fingerprint,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BUDGET_LINES"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_budget_rejects_bad_total_foreign_dependency_and_route_is_exposed():
    db, engine = _session()
    try:
        admin, org, run, prop, gl, lines = _fixture(db)
        bad_total = _record()
        bad_total["Details"][0]["TotalAmount"] = 1199
        result = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[bad_total]),
            db=db,
            current_user=admin,
        )
        assert result.invalid == 1
        assert "TotalAmount" in result.rows[0].reason

        foreign = _org(db, "Foreign Budget Org")
        gl.organization_id = foreign.id
        db.commit()
        result = api.dry_run_buildium_budgets(
            run.id,
            BuildiumBudgetDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert result.invalid == 1
        assert "INCOME or EXPENSE" in result.rows[0].reason

        from app.main import app
        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/budgets/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/budgets/commit" in paths
    finally:
        db.close()
        engine.dispose()
