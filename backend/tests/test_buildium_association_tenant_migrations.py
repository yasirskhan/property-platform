from __future__ import annotations
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.application import ApplicationPayment, LeaseApplication
from app.models.charge import Charge
from app.models.audit_log import AuditLog
from app.models.lease import Lease
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization, User, UserRole
from app.routers import buildium_association_tenant_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_association_tenant_migration import (
    BuildiumApiAssociationTenantCommitIn, BuildiumApiAssociationTenantDryRunIn,
    BuildiumAssociationTenantCommitIn, BuildiumAssociationTenantDryRunIn,
    BuildiumAssociationTenantResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult

def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine

def _admin(db):
    row = PlatformUser(
        email="buildium-hoa-tenant-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium", last_name="HoaTenant",
        role=PlatformUserRole.PLATFORM_ADMIN, is_active=True,
    )
    db.add(row); db.commit(); return row

def _org(db, name="HOA Tenant Org"):
    row = Organization(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    db.add(row); db.commit(); return row

def _tenant(db, org, *, email="jane.hoa.tenant@example.com", role=UserRole.TENANT):
    row = User(
        organization_id=org.id, email=email,
        hashed_password=hash_password("test-password"),
        first_name="Jane", last_name="Tenant", role=role,
        is_active=True, is_verified=True,
    )
    db.add(row); db.commit(); return row

def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id, provider="BUILDIUM",
        source_account_ref="buildium-hoa-tenants", status="DRAFT",
    )
    db.add(row); db.commit(); return row

def _record(**changes):
    row = {
        "Id": 8801, "FirstName": "Jane", "LastName": "Tenant",
        "Email": "jane.hoa.tenant@example.com",
        "AlternateEmail": "PRIVATE-ALT@example.com",
        "PhoneNumbers": [{"Number": "PRIVATE-PHONE", "Type": "Mobile"}],
        "PrimaryAddress": {"AddressLine1": "PRIVATE ADDRESS"},
        "OwnershipAccounts": [{"Id": 501, "AssociationId": 7, "UnitId": 9}],
        "MoveInDate": "2025-01-01", "MoveOutDate": None,
        "EmergencyContact": {"Name": "PRIVATE EMERGENCY"},
    }
    row.update(changes)
    return row

def test_buildium_association_tenant_existing_identity_reconciles_and_replays_without_customer_mutation():
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); target = _tenant(db, org); run = _run(db, org)
        users_before = db.query(User).count()
        apps_before = db.query(LeaseApplication).count()
        payments_before = db.query(ApplicationPayment).count()
        leases_before = db.query(Lease).count()
        charges_before = db.query(Charge).count()
        gl_before = db.query(GLTransaction).count()

        preview = api.dry_run_buildium_association_tenants(
            run.id, BuildiumAssociationTenantDryRunIn(records=[_record()]),
            db=db, current_user=admin,
        )
        assert preview.invalid == 0 and preview.reviewable == 1
        assert preview.rows[0].mapped["email"] == "jane.hoa.tenant@example.com"
        resolution = BuildiumAssociationTenantResolutionIn(
            source_id=8801, action="MATCH_EXISTING",
            target_tenant_user_id=target.id,
        )
        reviewed = api.dry_run_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        committed = api.commit_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()],
                resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "HOA_TENANTS"
        ).one()
        assert mapping.target_entity == "TENANT_USER"
        assert mapping.target_id == target.id
        assert db.query(User).count() == users_before
        assert db.query(LeaseApplication).count() == apps_before
        assert db.query(ApplicationPayment).count() == payments_before
        assert db.query(Lease).count() == leases_before
        assert db.query(Charge).count() == charges_before
        assert db.query(GLTransaction).count() == gl_before

        replay_preview = api.dry_run_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        replay = api.commit_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantCommitIn(
                fingerprint=replay_preview.fingerprint, records=[_record()],
                resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True

        items = base_api.list_migration_items(
            run.id, response=Response(), resource="hoa_tenants", limit=20,
            db=db, current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == target.email

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run").all()
        )
        assert "PRIVATE ADDRESS" not in audit
        assert "PRIVATE-PHONE" not in audit
        assert target.email not in audit
    finally:
        db.close(); engine.dispose()

def test_buildium_association_tenant_review_is_scoped_and_target_drift_invalidates_fingerprint():
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); target = _tenant(db, org); run = _run(db, org)
        foreign_org = _org(db, "Foreign HOA Tenant Org")
        foreign = _tenant(db, foreign_org, email="foreign.hoa.tenant@example.com")
        wrong_role = _tenant(db, org, email="owner-shaped@example.com", role=UserRole.OWNER)

        for bad_target in (foreign.id, wrong_role.id):
            with pytest.raises(HTTPException) as exc:
                api.dry_run_buildium_association_tenants(
                    run.id,
                    BuildiumAssociationTenantDryRunIn(
                        records=[_record()],
                        resolutions=[BuildiumAssociationTenantResolutionIn(
                            source_id=8801, action="MATCH_EXISTING",
                            target_tenant_user_id=bad_target,
                        )],
                    ),
                    db=db, current_user=admin,
                )
            assert exc.value.status_code == 409

        resolution = BuildiumAssociationTenantResolutionIn(
            source_id=8801, action="MATCH_EXISTING",
            target_tenant_user_id=target.id,
        )
        reviewed = api.dry_run_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        target.first_name = "Changed"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_association_tenants(
                run.id,
                BuildiumAssociationTenantCommitIn(
                    fingerprint=reviewed.fingerprint, records=[_record()],
                    resolutions=[resolution],
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "fingerprint" in exc.value.detail.lower()
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "HOA_TENANTS"
        ).count() == 0
    finally:
        db.close(); engine.dispose()

def test_buildium_association_tenant_skip_validation_and_routes():
    from app.main import app
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); _tenant(db, org); run = _run(db, org)
        skip = BuildiumAssociationTenantResolutionIn(source_id=8801, action="SKIP")
        reviewed = api.dry_run_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantDryRunIn(records=[_record()], resolutions=[skip]),
            db=db, current_user=admin,
        )
        result = api.commit_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()],
                resolutions=[skip],
            ),
            db=db, current_user=admin,
        )
        assert result.matched_existing == 0 and result.skipped_review == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "HOA_TENANTS"
        ).count() == 0

        invalid = api.dry_run_buildium_association_tenants(
            run.id,
            BuildiumAssociationTenantDryRunIn(records=[_record(Email="not-an-email")]),
            db=db, current_user=admin,
        )
        assert invalid.invalid == 1

        with pytest.raises(ValidationError):
            BuildiumAssociationTenantDryRunIn(records=[_record()], access_token="secret")

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/hoa-tenants/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/hoa-tenants/commit" in paths
    finally:
        db.close(); engine.dispose()



class _AssociationTenantApiResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_association_tenant_api_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "hoa-tenant-client")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "hoa-tenant-secret")
    monkeypatch.setattr(
        transport.settings,
        "BUILDIUM_API_SOURCE_ACCOUNT_REF",
        "buildium-hoa-tenants",
    )


def test_buildium_transport_fetches_bounded_association_tenants(monkeypatch):
    _configure_association_tenant_api_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        assert url == "https://apisandbox.buildium.com/v1/associations/tenants"
        return _AssociationTenantApiResponse(200, [_record()])

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_association_tenants(
        expected_source_account_ref="buildium-hoa-tenants"
    )
    assert result.records == [_record()]
    assert result.request_count == 1
    assert calls[0][2] == {"offset": 0, "limit": 500}
    assert calls[0][1]["x-buildium-client-secret"] == "hoa-tenant-secret"


def test_buildium_api_association_tenant_maps_existing_replays_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); target = _tenant(db, org); run = _run(db, org)
        before = (
            db.query(User).count(),
            db.query(LeaseApplication).count(),
            db.query(ApplicationPayment).count(),
            db.query(Lease).count(),
            db.query(Charge).count(),
            db.query(GLTransaction).count(),
        )

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "buildium-hoa-tenants"
            return BuildiumApiFetchResult(
                records=[_record()], mode="sandbox", request_count=1
            )

        monkeypatch.setattr(api, "fetch_association_tenants", fetched)
        resolution = BuildiumAssociationTenantResolutionIn(
            source_id=8801, action="MATCH_EXISTING",
            target_tenant_user_id=target.id,
        )
        reviewed = api.api_dry_run_buildium_association_tenants(
            run.id,
            BuildiumApiAssociationTenantDryRunIn(resolutions=[resolution]),
            db=db, current_user=admin,
        )
        assert reviewed.invalid == 0 and reviewed.reviewable == 1

        committed = api.api_commit_buildium_association_tenants(
            run.id,
            BuildiumApiAssociationTenantCommitIn(
                fingerprint=reviewed.fingerprint, resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 1
        replay = api.api_commit_buildium_association_tenants(
            run.id,
            BuildiumApiAssociationTenantCommitIn(
                fingerprint=reviewed.fingerprint, resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert replay.replayed is True
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "HOA_TENANTS"
        ).count() == 1
        assert before == (
            db.query(User).count(),
            db.query(LeaseApplication).count(),
            db.query(ApplicationPayment).count(),
            db.query(Lease).count(),
            db.query(Charge).count(),
            db.query(GLTransaction).count(),
        )

        with pytest.raises(ValidationError):
            BuildiumApiAssociationTenantDryRunIn(records=[_record()])
        with pytest.raises(ValidationError):
            BuildiumApiAssociationTenantCommitIn(
                fingerprint=reviewed.fingerprint, access_token="secret"
            )

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run").all()
        )
        assert "PRIVATE ADDRESS" not in audit
        assert "PRIVATE-PHONE" not in audit
        assert "PRIVATE EMERGENCY" not in audit
        assert "PRIVATE-ALT" not in audit
        assert "hoa-tenant-secret" not in audit
        assert "provider_private_tenant_data_stored" in audit
        assert "provider_ownership_data_stored" in audit
        assert "provider_move_history_stored" in audit
    finally:
        db.close(); engine.dispose()


def test_buildium_api_association_tenant_provider_and_target_drift_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); target = _tenant(db, org); run = _run(db, org)
        state = {"email": "jane.hoa.tenant@example.com"}

        def fetched(*, expected_source_account_ref):
            return BuildiumApiFetchResult(
                records=[_record(Email=state["email"])],
                mode="sandbox", request_count=1,
            )

        monkeypatch.setattr(api, "fetch_association_tenants", fetched)
        resolution = BuildiumAssociationTenantResolutionIn(
            source_id=8801, action="MATCH_EXISTING",
            target_tenant_user_id=target.id,
        )
        reviewed = api.api_dry_run_buildium_association_tenants(
            run.id,
            BuildiumApiAssociationTenantDryRunIn(resolutions=[resolution]),
            db=db, current_user=admin,
        )
        state["email"] = "changed.hoa.tenant@example.com"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_association_tenants(
                run.id,
                BuildiumApiAssociationTenantCommitIn(
                    fingerprint=reviewed.fingerprint, resolutions=[resolution],
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "HOA_TENANTS"
        ).count() == 0

        state["email"] = "jane.hoa.tenant@example.com"
        reviewed = api.api_dry_run_buildium_association_tenants(
            run.id,
            BuildiumApiAssociationTenantDryRunIn(resolutions=[resolution]),
            db=db, current_user=admin,
        )
        target.first_name = "Changed"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_association_tenants(
                run.id,
                BuildiumApiAssociationTenantCommitIn(
                    fingerprint=reviewed.fingerprint, resolutions=[resolution],
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "HOA_TENANTS"
        ).count() == 0
    finally:
        db.close(); engine.dispose()


def test_buildium_api_association_tenant_routes_and_status(monkeypatch):
    from app.main import app
    db, engine = _session()
    try:
        admin = _admin(db)
        monkeypatch.setattr(
            base_api,
            "transport_status",
            lambda: type(
                "TransportState", (),
                {"mode": "sandbox", "configured": True, "source_account_bound": True},
            )(),
        )
        status = base_api.get_buildium_transport_status(current_user=admin)
        assert "HOA_TENANTS" in status.supported_resources
        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/hoa-tenants/api-dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/hoa-tenants/api-commit" in paths
    finally:
        db.close(); engine.dispose()
