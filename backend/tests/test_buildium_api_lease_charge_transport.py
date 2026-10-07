from __future__ import annotations

from datetime import date
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
from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiLeaseChargeCommitIn,
    BuildiumApiLeaseChargeDryRunIn,
    BuildiumLeaseChargeResolutionIn,
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
        email="buildium-api-lease-charge-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="LeaseCharge",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Lease Charge Target",
        slug="buildium-api-lease-charge-target",
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


def _provider_record(**changes):
    row = {
        "Id": 8001,
        "Date": "2026-02-05",
        "TotalAmount": 75,
        "Memo": "Late fee",
        "BillId": None,
        "Lines": [
            {
                "Amount": 75,
                "GLAccountId": 7001,
                "UnitId": 2001,
            }
        ],
    }
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="Mapped Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="10 Lake Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="United States",
        is_active=True,
    )
    db.add(prop)
    db.flush()

    unit = Unit(
        property_id=prop.id,
        unit_number="1A",
        bedrooms=2,
        bathrooms=1.5,
        square_feet=900,
        monthly_rent=1250,
        is_available=None,
        is_listed=True,
        is_active=True,
    )
    db.add(unit)
    db.flush()

    tenant = User(
        email="lease-charge-tenant@example.com",
        hashed_password=hash_password("tenant-password"),
        first_name="Tina",
        last_name="Tenant",
        role=UserRole.TENANT,
        organization_id=run.organization_id,
        is_active=True,
        is_verified=True,
    )
    db.add(tenant)
    db.flush()

    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=1300,
        security_deposit=500,
        due_day=1,
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease)
    db.flush()

    gl = GLAccount(
        organization_id=run.organization_id,
        gl_number="4105",
        name="Late Fee Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add(gl)
    db.flush()

    for resource, source_id, entity, target_id, fp in (
        ("PROPERTIES", "1001", "PROPERTY", prop.id, "a" * 64),
        ("UNITS", "2001", "UNIT", unit.id, "b" * 64),
        ("TENANTS", "5001", "TENANT_USER", tenant.id, "c" * 64),
        ("LEASES", "6001", "LEASE_RELATIONSHIP", lease.id, "d" * 64),
        ("GL_ACCOUNTS", "7001", "GL_ACCOUNT", gl.id, "e" * 64),
    ):
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource=resource,
                source_id=source_id,
                target_entity=entity,
                target_id=target_id,
                source_fingerprint=fp,
            )
        )

    charge = Charge(
        organization_id=run.organization_id,
        tenant_user_id=tenant.id,
        unit_id=unit.id,
        property_id=prop.id,
        gl_account_id=gl.id,
        charge_date=date(2026, 2, 5),
        description="Late fee",
        amount=Decimal("75.00"),
        amount_paid=Decimal("25.00"),
        is_paid=False,
        is_active=True,
    )
    db.add(charge)
    db.commit()
    return prop, unit, tenant, lease, gl, charge


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_CLIENT_SECRET", "lease-charge-secret"
    )
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )


def test_buildium_transport_fetches_bounded_nested_lease_charges(monkeypatch):
    _configure_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        if url.endswith("/v1/leases/6001/charges"):
            return _Response(200, [_provider_record(LeaseId=999999)])
        if url.endswith("/v1/leases/6002/charges"):
            return _Response(200, [])
        raise AssertionError(url)

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_lease_charges(
        expected_source_account_ref="sandbox-account-A",
        parent_lease_ids=["6002", "6001"],
    )
    assert result.records[0]["Id"] == 8001
    assert result.records[0]["LeaseId"] == 6001
    assert result.parent_record_count == 2
    assert result.request_count == 2
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/leases/6001/charges"
    assert calls[0][2] == {"offset": 0, "limit": 501}
    assert calls[1][0] == "https://apisandbox.buildium.com/v1/leases/6002/charges"
    assert calls[0][1]["x-buildium-client-secret"] == "lease-charge-secret"

    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_lease_charges(
            expected_source_account_ref="sandbox-account-A",
            parent_lease_ids=list(
                range(1, transport.MAX_LEASE_CHARGE_PARENT_LEASES + 2)
            ),
        )
    assert exc.value.code == "source_too_large"

    def too_many(url, *, headers, params, timeout):
        return _Response(
            200,
            [
                _provider_record(Id=9000 + index)
                for index in range(transport.MAX_LEASE_CHARGE_RECORDS + 1)
            ],
        )

    monkeypatch.setattr(transport.requests, "get", too_many)
    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_lease_charges(
            expected_source_account_ref="sandbox-account-A",
            parent_lease_ids=[6001],
        )
    assert exc.value.code == "source_too_large"


def test_buildium_api_lease_charge_maps_existing_only_replays_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, _, _, _, _, charge = _target(db, run)
        gl_count = db.query(GLTransaction).count()

        def fetched(*, expected_source_account_ref, parent_lease_ids):
            assert expected_source_account_ref == "sandbox-account-A"
            assert parent_lease_ids == ["6001"]
            return BuildiumApiFetchResult(
                records=[{**_provider_record(), "LeaseId": 6001}],
                mode="sandbox",
                request_count=1,
                parent_record_count=1,
            )

        monkeypatch.setattr(api, "fetch_lease_charges", fetched)
        resolution = BuildiumLeaseChargeResolutionIn(
            source_id=8001,
            action="MATCH_EXISTING",
            target_charge_id=charge.id,
        )
        reviewed = api.api_dry_run_buildium_lease_charges(
            run.id,
            BuildiumApiLeaseChargeDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.rows[0].mapped["target_charge_id"] if "target_charge_id" in reviewed.rows[0].mapped else charge.id

        committed = api.api_commit_buildium_lease_charges(
            run.id,
            BuildiumApiLeaseChargeCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "LEASE_CHARGES")
            .one()
        )
        assert mapping.target_entity == "CHARGE_RELATIONSHIP"
        assert mapping.target_id == charge.id
        assert db.query(Charge).count() == 1
        assert db.query(GLTransaction).count() == gl_count
        db.refresh(charge)
        assert Decimal(charge.amount_paid) == Decimal("25.00")
        assert charge.is_paid is False

        replay = api.api_commit_buildium_lease_charges(
            run.id,
            BuildiumApiLeaseChargeCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASE_CHARGES"
        ).count() == 1

        with pytest.raises(ValidationError):
            BuildiumApiLeaseChargeDryRunIn(records=[_provider_record()])
        with pytest.raises(ValidationError):
            BuildiumApiLeaseChargeCommitIn(
                fingerprint=reviewed.fingerprint,
                client_secret="secret",
            )

        audit = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "Late fee" not in audit
        assert "lease-charge-secret" not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()
        assert '"provider_memo_stored":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_lease_charge_provider_dependency_and_target_drift_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, _, _, _, _, charge = _target(db, run)
        state = {"memo": "Late fee"}

        def fetched(*, expected_source_account_ref, parent_lease_ids):
            assert parent_lease_ids == ["6001"]
            return BuildiumApiFetchResult(
                records=[
                    {
                        **_provider_record(Memo=state["memo"]),
                        "LeaseId": 6001,
                    }
                ],
                mode="sandbox",
                request_count=1,
                parent_record_count=1,
            )

        monkeypatch.setattr(api, "fetch_lease_charges", fetched)
        resolution = BuildiumLeaseChargeResolutionIn(
            source_id=8001,
            action="MATCH_EXISTING",
            target_charge_id=charge.id,
        )
        reviewed = api.api_dry_run_buildium_lease_charges(
            run.id,
            BuildiumApiLeaseChargeDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )

        state["memo"] = "Changed provider memo"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_lease_charges(
                run.id,
                BuildiumApiLeaseChargeCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower() or "match" in exc.value.detail.lower()
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASE_CHARGES"
        ).count() == 0

        state["memo"] = "Late fee"
        reviewed = api.api_dry_run_buildium_lease_charges(
            run.id,
            BuildiumApiLeaseChargeDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        lease_mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASES"
        ).one()
        lease_mapping.source_fingerprint = "z" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_lease_charges(
                run.id,
                BuildiumApiLeaseChargeCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()

        lease_mapping.source_fingerprint = "d" * 64
        db.commit()
        reviewed = api.api_dry_run_buildium_lease_charges(
            run.id,
            BuildiumApiLeaseChargeDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        charge.description = "Changed target description"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_lease_charges(
                run.id,
                BuildiumApiLeaseChargeCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "match" in exc.value.detail.lower() or "changed" in exc.value.detail.lower()
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASE_CHARGES"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_lease_charge_parent_scope_routes_and_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _target(db, run)

        assert api._lease_charge_api_parent_source_ids(db, run=run) == ["6001"]

        bad = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASES"
        ).one()
        bad.target_entity = "WRONG"
        db.commit()
        with pytest.raises(Exception) as exc:
            api._lease_charge_api_parent_source_ids(db, run=run)
        assert "inconsistent" in str(exc.value).lower()

        monkeypatch.setattr(
            api,
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
        status = api.get_buildium_transport_status(current_user=admin)
        assert "LEASE_CHARGES" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/lease-charges/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/lease-charges/api-commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
