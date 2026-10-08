from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.lease import Lease, LeaseStatus
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, Unit
from app.models.tenant_insurance import TenantInsurance, TenantInsuranceStatus
from app.models.user import Organization, User, UserRole
from app.routers import buildium_migrations as base_api
from app.routers import buildium_renters_insurance_migrations as api
from app.schemas.buildium_renters_insurance_migration import (
    BuildiumApiRentersInsuranceCommitIn,
    BuildiumApiRentersInsuranceDryRunIn,
    BuildiumRentersInsuranceCommitIn,
    BuildiumRentersInsuranceDryRunIn,
    BuildiumRentersInsuranceResolutionIn,
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


def _admin(db):
    row = PlatformUser(
        email="buildium-insurance-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Insurance",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(
        name="Buildium Insurance Org",
        slug="buildium-insurance-org",
        is_active=True,
    )
    db.add(org)
    db.flush()
    prop = Property(
        organization_id=org.id,
        name="Insurance Apartments",
        property_type="multi_family",
        address_line1="10 Policy Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    tenant = User(
        organization_id=org.id,
        email="insured-tenant@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Insured",
        last_name="Tenant",
        role=UserRole.TENANT,
        is_active=True,
    )
    db.add_all([prop, tenant])
    db.flush()
    unit = Unit(property_id=prop.id, unit_number="101", is_active=True)
    db.add(unit)
    db.flush()
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=1500,
        security_deposit=1500,
        due_day=1,
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease)
    db.flush()
    policy = TenantInsurance(
        lease_id=lease.id,
        tenant_id=tenant.id,
        property_id=prop.id,
        provider="Safe Harbor Insurance",
        policy_number="POL-2026-77",
        effective_date=date(2026, 1, 1),
        expiration_date=date(2026, 12, 31),
        status=TenantInsuranceStatus.VERIFIED,
    )
    db.add(policy)
    db.flush()
    run = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-renters-insurance",
        status="DRAFT",
    )
    db.add(run)
    db.flush()
    lease_mapping = PlatformMigrationItem(
        run_id=run.id,
        organization_id=org.id,
        provider="BUILDIUM",
        resource="LEASES",
        source_id="5001",
        target_entity="LEASE_RELATIONSHIP",
        target_id=lease.id,
        source_fingerprint="1" * 64,
    )
    tenant_mapping = PlatformMigrationItem(
        run_id=run.id,
        organization_id=org.id,
        provider="BUILDIUM",
        resource="TENANTS",
        source_id="6001",
        target_entity="TENANT_USER",
        target_id=tenant.id,
        source_fingerprint="2" * 64,
    )
    db.add_all([lease_mapping, tenant_mapping])
    db.commit()
    return org, prop, unit, tenant, lease, policy, run, lease_mapping, tenant_mapping


def _record(**changes):
    row = {
        "Id": 9701,
        "SourceLeaseId": 5001,
        "InsuranceCompany": "Safe Harbor Insurance",
        "CarrierType": "ThirdParty",
        "PolicyIdentifier": "POL-2026-77",
        "EffectiveDate": "2026-01-01",
        "ExpirationDate": "2026-12-31",
        "CancellationDate": None,
        "InsuredTenants": [
            {
                "Id": 6001,
                "FirstName": "Insured",
                "LastName": "Tenant",
                "IsPrimaryInsured": True,
            }
        ],
        "RawNote": "DO-NOT-AUDIT-INSURANCE-RAW",
    }
    row.update(changes)
    return row


def test_buildium_renters_insurance_reconciles_exact_existing_policy_and_replays():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, prop, _, _, _, policy, run, _, _ = _fixture(db)
        before_count = db.query(TenantInsurance).count()

        preview = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_lease_id"] == policy.lease_id
        assert preview.rows[0].mapped["target_tenant_id"] == policy.tenant_id

        resolution = BuildiumRentersInsuranceResolutionIn(
            source_id=9701,
            action="MATCH_EXISTING",
            target_tenant_insurance_id=policy.id,
        )
        reviewed = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.resource == "RENTERS_INSURANCE",
            )
            .one()
        )
        assert mapping.target_entity == "TENANT_INSURANCE_RELATIONSHIP"
        assert mapping.target_id == policy.id
        assert db.query(TenantInsurance).count() == before_count

        replay_preview = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True
        assert db.query(TenantInsurance).count() == before_count

        response = Response()
        items = base_api.list_migration_items(
            run.id,
            response=response,
            resource="renters_insurance",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == (
            f"Tenant Insurance #{policy.id}: POL-2026-77"
        )

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-AUDIT-INSURANCE-RAW" not in audit_text
        assert "POL-2026-77" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_renters_insurance_blocks_lossy_shapes_and_stale_state():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, _, policy, run, lease_mapping, _ = _fixture(db)

        multi = _record(
            InsuredTenants=[
                {"Id": 6001},
                {"Id": 6002},
            ]
        )
        blocked = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(records=[multi]),
            db=db,
            current_user=admin,
        )
        assert blocked.invalid == 1
        assert "exactly one" in blocked.rows[0].reason

        cancelled = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(
                records=[_record(CancellationDate="2026-06-01")]
            ),
            db=db,
            current_user=admin,
        )
        assert cancelled.invalid == 1
        assert "cancellation-date" in cancelled.rows[0].reason

        resolution = BuildiumRentersInsuranceResolutionIn(
            source_id=9701,
            action="MATCH_EXISTING",
            target_tenant_insurance_id=policy.id,
        )
        reviewed = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        lease_mapping.source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_renters_insurance(
                run.id,
                BuildiumRentersInsuranceCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "fingerprint" in exc.value.detail.lower()

        lease_mapping.source_fingerprint = "1" * 64
        db.commit()
        reviewed = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        policy.expiration_date = date(2027, 1, 31)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_renters_insurance(
                run.id,
                BuildiumRentersInsuranceCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
    finally:
        db.close()
        engine.dispose()


def test_buildium_renters_insurance_skip_cross_org_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        _, prop, _, _, _, policy, run, _, _ = _fixture(db)

        skip = BuildiumRentersInsuranceResolutionIn(
            source_id=9701,
            action="SKIP",
        )
        reviewed = api.dry_run_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceDryRunIn(
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_renters_insurance(
            run.id,
            BuildiumRentersInsuranceCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 0
        assert committed.skipped_review == 1
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "RENTERS_INSURANCE")
            .count()
            == 0
        )

        other = Organization(
            name="Other Insurance Org",
            slug="other-insurance-org",
            is_active=True,
        )
        db.add(other)
        db.flush()
        prop.organization_id = other.id
        db.commit()
        resolution = BuildiumRentersInsuranceResolutionIn(
            source_id=9701,
            action="MATCH_EXISTING",
            target_tenant_insurance_id=policy.id,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_renters_insurance(
                run.id,
                BuildiumRentersInsuranceDryRunIn(
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/renters-insurance/dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/renters-insurance/commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()



class _InsuranceApiResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_insurance_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "test-client")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "test-value")
    monkeypatch.setattr(
        transport.settings,
        "BUILDIUM_API_SOURCE_ACCOUNT_REF",
        "buildium-renters-insurance",
    )


def test_buildium_api_fetches_bounded_nested_renters_insurance(monkeypatch):
    _configure_insurance_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, timeout, params=None):
        calls.append((url, params.copy()))
        if url.endswith("/v1/leases/5001/rentersinsurance"):
            row = _record()
            row["SourceLeaseId"] = 999999
            return _InsuranceApiResponse(200, [row])
        raise AssertionError(url)

    monkeypatch.setattr(transport.requests, "get", fake_get)
    fetched = transport.fetch_renters_insurance(
        expected_source_account_ref="buildium-renters-insurance",
        parent_lease_ids=["5001"],
    )
    assert fetched.records[0]["Id"] == 9701
    assert fetched.records[0]["SourceLeaseId"] == 5001
    assert fetched.parent_record_count == 1
    assert fetched.request_count == 1
    assert calls[0] == (
        "https://apisandbox.buildium.com/v1/leases/5001/rentersinsurance",
        {"offset": 0, "limit": transport.MAX_RENTERS_INSURANCE_RECORDS + 1},
    )

    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_renters_insurance(
            expected_source_account_ref="buildium-renters-insurance",
            parent_lease_ids=list(
                range(1, transport.MAX_RENTERS_INSURANCE_PARENT_LEASES + 2)
            ),
        )
    assert exc.value.code == "source_too_large"


def test_buildium_api_renters_insurance_reconciles_replays_and_fails_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, _, policy, run, lease_mapping, _ = _fixture(db)
        state = {"expiration": "2026-12-31"}

        def fetched(*, expected_source_account_ref, parent_lease_ids):
            assert expected_source_account_ref == "buildium-renters-insurance"
            assert parent_lease_ids == ["5001"]
            return BuildiumApiFetchResult(
                records=[_record(ExpirationDate=state["expiration"])],
                mode="sandbox",
                request_count=1,
                parent_record_count=1,
            )

        monkeypatch.setattr(api, "fetch_renters_insurance", fetched)
        resolution = BuildiumRentersInsuranceResolutionIn(
            source_id=9701,
            action="MATCH_EXISTING",
            target_tenant_insurance_id=policy.id,
        )
        reviewed = api.api_dry_run_buildium_renters_insurance(
            run.id,
            BuildiumApiRentersInsuranceDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        committed = api.api_commit_buildium_renters_insurance(
            run.id,
            BuildiumApiRentersInsuranceCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        replay = api.api_commit_buildium_renters_insurance(
            run.id,
            BuildiumApiRentersInsuranceCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True

        state["expiration"] = "2027-01-31"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_renters_insurance(
                run.id,
                BuildiumApiRentersInsuranceCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        state["expiration"] = "2026-12-31"
        reviewed = api.api_dry_run_buildium_renters_insurance(
            run.id,
            BuildiumApiRentersInsuranceDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        lease_mapping.source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_renters_insurance(
                run.id,
                BuildiumApiRentersInsuranceCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        with pytest.raises(ValidationError):
            BuildiumApiRentersInsuranceDryRunIn(records=[_record()])
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_renters_insurance_scope_routes_and_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, _, _, run, _, _ = _fixture(db)
        assert api._renters_insurance_api_parent_source_ids(db, run=run) == ["5001"]

        monkeypatch.setattr(
            base_api,
            "transport_status",
            lambda: type(
                "TransportState",
                (),
                {"mode": "sandbox", "configured": True, "source_account_bound": True},
            )(),
        )
        status = base_api.get_buildium_transport_status(current_user=admin)
        assert "RENTERS_INSURANCE" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/renters-insurance/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/renters-insurance/api-commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
