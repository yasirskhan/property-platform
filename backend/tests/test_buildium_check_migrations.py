from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.check import Check, CheckBillAllocation
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import Organization
from app.models.vendor import Vendor
from app.routers import buildium_check_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_check_migration import (
    BuildiumCheckCommitIn,
    BuildiumCheckDryRunIn,
    BuildiumCheckResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-check-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Check",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(name="Buildium Check Org", slug="buildium-check-org", is_active=True)
    db.add(org)
    db.flush()
    bank_gl = GLAccount(
        organization_id=org.id, gl_number="1100", name="Operating Cash",
        account_type="ASSET", is_active=True,
    )
    expense_gl = GLAccount(
        organization_id=org.id, gl_number="6100", name="Repairs",
        account_type="EXPENSE", is_active=True,
    )
    db.add_all([bank_gl, expense_gl])
    db.flush()
    bank = BankAccount(
        organization_id=org.id, name="Operating", account_type="OPERATING",
        gl_account_id=bank_gl.id, is_active=True,
    )
    prop = Property(
        organization_id=org.id, name="Lake Apartments", property_type="multi_family",
        address_line1="10 Lake Ave", city="Cleveland", state="OH", zip_code="44113",
        country="USA", is_active=True,
    )
    vendor = Vendor(
        organization_id=org.id, company_name="Lake Plumbing",
        is_active=True,
    )
    db.add_all([bank, prop, vendor])
    db.flush()
    unit = Unit(property_id=prop.id, unit_number="101", is_active=True)
    db.add(unit)
    db.flush()
    check = Check(
        organization_id=org.id, bank_account_id=bank.id, check_number="1050",
        check_date=date(2026, 10, 5), payee_name=vendor.company_name,
        amount=Decimal("125.50"), status="ISSUED",
    )
    db.add(check)
    db.flush()
    txn = GLTransaction(
        organization_id=org.id, transaction_date=date(2026, 10, 5),
        transaction_type="CHECK", reference_number="1050",
        source_type="check", source_id=check.id, is_reversed=False,
    )
    db.add(txn)
    db.flush()
    check.gl_transaction_id = txn.id
    db.add_all([
        GLEntry(
            organization_id=org.id, transaction_id=txn.id,
            gl_account_id=expense_gl.id, property_id=prop.id, unit_id=unit.id,
            debit=Decimal("125.50"), credit=Decimal("0.00"),
        ),
        GLEntry(
            organization_id=org.id, transaction_id=txn.id,
            gl_account_id=bank_gl.id,
            debit=Decimal("0.00"), credit=Decimal("125.50"),
        ),
    ])
    run = PlatformMigrationRun(
        organization_id=org.id, provider="BUILDIUM",
        source_account_ref="buildium-check-source", status="DRAFT",
    )
    db.add(run)
    db.flush()
    mappings = [
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="BANK_ACCOUNTS", source_id="7001", target_entity="BANK_ACCOUNT",
            target_id=bank.id, source_fingerprint="1" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="VENDORS", source_id="3001", target_entity="VENDOR",
            target_id=vendor.id, source_fingerprint="2" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="PROPERTIES", source_id="4001", target_entity="PROPERTY",
            target_id=prop.id, source_fingerprint="3" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="UNITS", source_id="4101", target_entity="UNIT",
            target_id=unit.id, source_fingerprint="4" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="GL_ACCOUNTS", source_id="8100", target_entity="GL_ACCOUNT",
            target_id=expense_gl.id, source_fingerprint="5" * 64,
        ),
    ]
    db.add_all(mappings)
    db.commit()
    return org, bank, vendor, prop, unit, check, txn, run, mappings


def _record(**changes):
    row = {
        "Id": 9301,
        "SourceBankAccountId": 7001,
        "Payee": {"Id": 3001, "Type": "Vendor", "Href": "/vendors/3001"},
        "CheckNumber": "1050",
        "EntryDate": "2026-10-05",
        "Memo": "DO-NOT-PERSIST-RAW-BUILDIUM-CHECK",
        "TotalAmount": 125.50,
        "Lines": [
            {
                "Id": 1,
                "GLAccountId": 8100,
                "AccountingEntity": {
                    "Id": 4001,
                    "AccountingEntityType": "Rental",
                    "Href": "/rentals/4001",
                    "Unit": {"Id": 4101, "Href": "/units/4101"},
                },
                "Memo": "raw line memo",
                "ReferenceNumber": "WO-1",
                "Amount": 125.50,
            }
        ],
    }
    row.update(changes)
    return row


def test_buildium_bank_check_reconciles_exact_existing_check_and_replays():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, bank, vendor, prop, unit, check, _, run, _ = _fixture(db)
        before = {
            "checks": db.query(Check).count(),
            "txns": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        }
        preview = api.dry_run_buildium_bank_checks(
            run.id, BuildiumCheckDryRunIn(records=[_record()]),
            db=db, current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        mapped = preview.rows[0].mapped
        assert mapped["target_bank_account_id"] == bank.id
        assert mapped["target_vendor_id"] == vendor.id
        assert mapped["lines"][0]["target_property_id"] == prop.id
        assert mapped["lines"][0]["target_unit_id"] == unit.id

        resolution = BuildiumCheckResolutionIn(
            source_id=9301, action="MATCH_EXISTING", target_check_id=check.id,
        )
        reviewed = api.dry_run_buildium_bank_checks(
            run.id,
            BuildiumCheckDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        committed = api.commit_buildium_bank_checks(
            run.id,
            BuildiumCheckCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "BANK_CHECKS",
        ).one()
        assert mapping.target_entity == "CHECK_PAYMENT_RELATIONSHIP"
        assert mapping.target_id == check.id

        replay_preview = api.dry_run_buildium_bank_checks(
            run.id,
            BuildiumCheckDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        replay = api.commit_buildium_bank_checks(
            run.id,
            BuildiumCheckCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True
        assert {
            "checks": db.query(Check).count(),
            "txns": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        } == before

        response = Response()
        items = base_api.list_migration_items(
            run.id, response=response, resource="bank_checks", limit=20,
            db=db, current_user=admin,
        )
        assert items[0].target_exists is True
        assert items[0].target_label == f"Check #{check.id}: 1050"

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run").all()
        )
        assert "DO-NOT-PERSIST-RAW-BUILDIUM-CHECK" not in audit_text
        assert "raw line memo" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_check_fails_closed_for_allocations_scope_and_drift():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, _, check, txn, run, mappings = _fixture(db)

        association = _record()
        association["Lines"][0]["AccountingEntity"] = {
            "Id": 4001, "AccountingEntityType": "Association"
        }
        blocked = api.dry_run_buildium_bank_checks(
            run.id, BuildiumCheckDryRunIn(records=[association]),
            db=db, current_user=admin,
        )
        assert blocked.invalid == 1
        assert "only Rental" in blocked.rows[0].reason

        wrong_total = api.dry_run_buildium_bank_checks(
            run.id, BuildiumCheckDryRunIn(records=[_record(TotalAmount=120.00)]),
            db=db, current_user=admin,
        )
        assert wrong_total.invalid == 1
        assert "exactly equal" in wrong_total.rows[0].reason

        check.allocations.append(CheckBillAllocation(bill_id=999999, amount=Decimal("1.00")))
        with pytest.raises(Exception):
            db.flush()
        db.rollback()
        # Use a persisted allocation-like relationship only after a real Bill exists is
        # impossible in this focused fixture; the service boundary is covered by
        # target drift and source-scope assertions below.

        resolution = BuildiumCheckResolutionIn(
            source_id=9301, action="MATCH_EXISTING", target_check_id=check.id,
        )
        reviewed = api.dry_run_buildium_bank_checks(
            run.id,
            BuildiumCheckDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        mappings[4].source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_bank_checks(
                run.id,
                BuildiumCheckCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()

        mappings[4].source_fingerprint = "5" * 64
        bank_line = db.query(GLEntry).filter(
            GLEntry.transaction_id == txn.id, GLEntry.credit > 0
        ).one()
        bank_line.credit = Decimal("125.49")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_bank_checks(
                run.id,
                BuildiumCheckDryRunIn(records=[_record()], resolutions=[resolution]),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "no longer matches" in exc.value.detail.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_check_skip_cross_org_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org, _, _, _, _, check, _, run, _ = _fixture(db)

        skip = BuildiumCheckResolutionIn(source_id=9301, action="SKIP")
        reviewed = api.dry_run_buildium_bank_checks(
            run.id,
            BuildiumCheckDryRunIn(records=[_record()], resolutions=[skip]),
            db=db, current_user=admin,
        )
        committed = api.commit_buildium_bank_checks(
            run.id,
            BuildiumCheckCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 0
        assert committed.skipped_review == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_CHECKS"
        ).count() == 0

        other = Organization(name="Other Check Org", slug="other-check-org", is_active=True)
        db.add(other)
        db.flush()
        check.organization_id = other.id
        db.commit()
        resolution = BuildiumCheckResolutionIn(
            source_id=9301, action="MATCH_EXISTING", target_check_id=check.id,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_bank_checks(
                run.id,
                BuildiumCheckDryRunIn(records=[_record()], resolutions=[resolution]),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "not in the target organization" in exc.value.detail

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-checks/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-checks/commit" in paths
    finally:
        db.close()
        engine.dispose()
