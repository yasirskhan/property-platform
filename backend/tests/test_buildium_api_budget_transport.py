from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property
from app.models.property_budget import PropertyBudgetLine
from app.models.user import Organization
from app.routers import buildium_budget_migrations as api
from app.routers import buildium_migrations as core_api
from app.schemas.buildium_budget_migration import (
    BuildiumApiBudgetCommitIn,
    BuildiumApiBudgetDryRunIn,
    BuildiumBudgetResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import (
    BuildiumApiFetchResult,
    BuildiumApiTransportError,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_admin(db):
    row = PlatformUser(
        email="buildium-api-budget-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Budget",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Budget Target",
        slug="buildium-api-budget-target",
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="sandbox-account-A",
        status="DRAFT",
    )
    db.add(row)
    db.commit()
    return row


def _record(**changes):
    monthly = {
        name: 100
        for name in (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    }
    row = {
        "Id": 701,
        "Name": "2026 Private Operating Budget",
        "StartDate": "2026-01-01",
        "EndDate": "2026-12-31",
        "Property": {"Id": 501, "Type": "Rental", "Href": "/rentals/501"},
        "Details": [
            {
                "GLAccountId": 601,
                "GLAccountSubType": "Income",
                "TotalAmount": 1200,
                "MonthlyAmounts": monthly,
            }
        ],
    }
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="Budget Property",
        address_line1="100 Budget Way",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        is_active=True,
    )
    gl = GLAccount(
        organization_id=run.organization_id,
        gl_number="4100",
        name="Rent Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add_all([prop, gl])
    db.flush()

    db.add_all(
        [
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="PROPERTIES",
                source_id="501",
                target_entity="PROPERTY",
                target_id=prop.id,
                source_fingerprint="a" * 64,
            ),
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="GL_ACCOUNTS",
                source_id="601",
                target_entity="GL_ACCOUNT",
                target_id=gl.id,
                source_fingerprint="b" * 64,
            ),
        ]
    )

    lines = []
    for month in range(1, 13):
        line = PropertyBudgetLine(
            organization_id=run.organization_id,
            property_id=prop.id,
            gl_account_id=gl.id,
            calendar_year=2026,
            month=month,
            amount=Decimal("100.00"),
        )
        db.add(line)
        lines.append(line)
    db.commit()
    return prop, gl, lines


def _resolutions(lines):
    return [
        BuildiumBudgetResolutionIn(
            source_id=f"701:601:2026:{month}",
            action="MATCH_EXISTING",
            target_property_budget_line_id=line.id,
        )
        for month, line in enumerate(lines, start=1)
    ]


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "budget-secret")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )


def test_buildium_transport_fetches_bounded_budgets(monkeypatch):
    _configure_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_record()])

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_budgets(
        expected_source_account_ref="sandbox-account-A",
    )
    assert result.records == [_record()]
    assert result.mode == "sandbox"
    assert result.request_count == 1
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/budgets"
    assert calls[0][2] == {"offset": 0, "limit": 500}
    assert calls[0][1]["x-buildium-client-secret"] == "budget-secret"

    def too_many(url, *, headers, params, timeout):
        if params["offset"] == 0:
            return _Response(200, [_record(Id=index + 1) for index in range(500)])
        return _Response(200, [_record(Id=9999)])

    monkeypatch.setattr(transport.requests, "get", too_many)
    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_budgets(expected_source_account_ref="sandbox-account-A")
    assert exc.value.code == "source_too_large"


def test_buildium_api_budget_maps_existing_only_replays_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, _, lines = _target(db, run)
        before_amounts = [(line.id, str(line.amount), line.updated_at) for line in lines]
        before_gl = db.query(GLTransaction).count()

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_record()],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_budgets", fetched)
        resolutions = _resolutions(lines)
        reviewed = api.api_dry_run_buildium_budgets(
            run.id,
            BuildiumApiBudgetDryRunIn(resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 12

        committed = api.api_commit_buildium_budgets(
            run.id,
            BuildiumApiBudgetCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 12
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BUDGET_LINES",
            PlatformMigrationItem.target_entity == "PROPERTY_BUDGET_LINE",
        ).count() == 12
        assert [
            (line.id, str(db.get(PropertyBudgetLine, line.id).amount), db.get(PropertyBudgetLine, line.id).updated_at)
            for line in lines
        ] == before_amounts
        assert db.query(GLTransaction).count() == before_gl

        replay = api.api_commit_buildium_budgets(
            run.id,
            BuildiumApiBudgetCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BUDGET_LINES"
        ).count() == 12

        with pytest.raises(ValidationError):
            BuildiumApiBudgetDryRunIn(records=[_record()])
        with pytest.raises(ValidationError):
            BuildiumApiBudgetCommitIn(
                fingerprint=reviewed.fingerprint,
                client_secret="secret",
            )

        audit = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "2026 Private Operating Budget" not in audit
        assert "budget-secret" not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()
        assert '"provider_budget_name_stored":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_budget_provider_dependency_and_target_drift_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, _, lines = _target(db, run)
        state = {"name": "2026 Private Operating Budget"}

        def fetched(*, expected_source_account_ref):
            return BuildiumApiFetchResult(
                records=[_record(Name=state["name"])],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_budgets", fetched)
        resolutions = _resolutions(lines)
        reviewed = api.api_dry_run_buildium_budgets(
            run.id,
            BuildiumApiBudgetDryRunIn(resolutions=resolutions),
            db=db,
            current_user=admin,
        )

        state["name"] = "Changed Provider Budget"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_budgets(
                run.id,
                BuildiumApiBudgetCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        state["name"] = "2026 Private Operating Budget"
        reviewed = api.api_dry_run_buildium_budgets(
            run.id,
            BuildiumApiBudgetDryRunIn(resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        prop_mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "PROPERTIES"
        ).one()
        prop_mapping.source_fingerprint = "z" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_budgets(
                run.id,
                BuildiumApiBudgetCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        prop_mapping.source_fingerprint = "a" * 64
        db.commit()
        reviewed = api.api_dry_run_buildium_budgets(
            run.id,
            BuildiumApiBudgetDryRunIn(resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        lines[0].amount = Decimal("101.00")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_budgets(
                run.id,
                BuildiumApiBudgetCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=resolutions,
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


def test_buildium_api_budget_routes_and_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_admin(db)

        monkeypatch.setattr(
            core_api,
            "transport_status",
            lambda: type(
                "TransportState",
                (),
                {
                    "mode": "sandbox",
                    "configured": True,
                    "source_account_bound": True,
                },
            )(),
        )
        status = core_api.get_buildium_transport_status(current_user=admin)
        assert "BUDGETS" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/budgets/api-dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/budgets/api-commit" in paths
    finally:
        db.close()
        engine.dispose()
