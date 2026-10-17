from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiWorkOrderCommitIn,
    BuildiumApiWorkOrderDryRunIn,
    BuildiumWorkOrderResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-api-work-order-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="WorkOrder",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Work Order Target",
        slug="buildium-api-work-order-target",
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
    row = {
        "Id": 8001,
        "Title": "Kitchen sink leak",
        "Status": "Open",
        "DueDate": "2026-10-10",
        "Priority": "High",
        "VendorId": 4001,
        "EntryAllowed": True,
        "EntryNotes": "DO-NOT-PERSIST-API-ENTRY-NOTES",
        "Amount": 275.50,
        "BillTransactionIds": [99001],
        "LineItems": [
            {"Description": "DO-NOT-PROMOTE-API-LINE", "Amount": 275.50}
        ],
        "Task": {
            "Id": 7001,
            "PropertyId": 1001,
            "UnitId": 2001,
            "Description": "DO-NOT-PROMOTE-API-TASK-TEXT",
        },
    }
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="API Work Order Property",
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
    vendor = Vendor(
        organization_id=run.organization_id,
        company_name="API Plumbing Vendor",
        is_active=True,
    )
    tenant = User(
        email="buildium-api-work-order-tenant@example.com",
        hashed_password=hash_password("tenant-password"),
        first_name="Taylor",
        last_name="Tenant",
        role=UserRole.TENANT,
        organization_id=run.organization_id,
        is_active=True,
    )
    db.add_all([unit, vendor, tenant])
    db.flush()

    work_order = WorkOrder(
        unit_id=unit.id,
        tenant_id=tenant.id,
        property_id=prop.id,
        vendor_id=vendor.id,
        title="Kitchen sink leak",
        description="Existing local maintenance description",
        status=WorkOrderStatus.SUBMITTED,
        permission_to_enter=False,
    )
    db.add(work_order)
    db.flush()

    db.add_all(
        [
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="PROPERTIES",
                source_id="1001",
                target_entity="PROPERTY",
                target_id=prop.id,
                source_fingerprint="p" * 64,
            ),
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="UNITS",
                source_id="2001",
                target_entity="UNIT",
                target_id=unit.id,
                source_fingerprint="u" * 64,
            ),
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="VENDORS",
                source_id="4001",
                target_entity="VENDOR",
                target_id=vendor.id,
                source_fingerprint="v" * 64,
            ),
        ]
    )
    db.commit()
    return work_order


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_buildium_transport_fetches_work_orders_from_fixed_endpoint(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "work-order-secret")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_record()])

    monkeypatch.setattr(transport.requests, "get", fake_get)

    result = transport.fetch_work_orders(
        expected_source_account_ref="sandbox-account-A"
    )
    assert result.records[0]["Id"] == 8001
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/workorders"
    assert calls[0][1]["x-buildium-client-secret"] == "work-order-secret"
    assert calls[0][2] == {"offset": 0, "limit": 500}


def test_buildium_api_work_order_maps_existing_relationship_only_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        target = _target(db, run)
        original = {
            "tenant_id": target.tenant_id,
            "assigned_to_id": target.assigned_to_id,
            "status": target.status,
            "permission_to_enter": target.permission_to_enter,
            "total_cost": target.total_cost,
            "description": target.description,
        }

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_record()], mode="sandbox", request_count=1
            )

        monkeypatch.setattr(api, "fetch_work_orders", fetched)
        resolution = BuildiumWorkOrderResolutionIn(
            source_id=8001,
            action="MATCH_EXISTING",
            target_work_order_id=target.id,
        )
        reviewed = api.api_dry_run_buildium_work_orders(
            run.id,
            BuildiumApiWorkOrderDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1

        committed = api.api_commit_buildium_work_orders(
            run.id,
            BuildiumApiWorkOrderCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "WORK_ORDERS")
            .one()
        )
        assert mapping.target_entity == "WORK_ORDER_RELATIONSHIP"
        assert mapping.target_id == target.id
        assert db.query(WorkOrder).count() == 1
        assert db.query(GLTransaction).count() == 0

        db.refresh(target)
        assert target.tenant_id == original["tenant_id"]
        assert target.assigned_to_id == original["assigned_to_id"]
        assert target.status == original["status"]
        assert target.permission_to_enter == original["permission_to_enter"]
        assert target.total_cost == original["total_cost"]
        assert target.description == original["description"]

        with pytest.raises(ValidationError):
            BuildiumApiWorkOrderDryRunIn(client_secret="secret")
        with pytest.raises(ValidationError):
            BuildiumApiWorkOrderCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
            )

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-API-ENTRY-NOTES" not in audit
        assert "DO-NOT-PROMOTE-API-TASK-TEXT" not in audit
        assert "DO-NOT-PROMOTE-API-LINE" not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_work_order_commit_refetch_detects_drift_and_routes_exist(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        target = _target(db, run)
        resolution = BuildiumWorkOrderResolutionIn(
            source_id=8001,
            action="MATCH_EXISTING",
            target_work_order_id=target.id,
        )
        state = {"changed": False}

        def fetched(*, expected_source_account_ref):
            record = (
                _record(Title="Provider title changed after review")
                if state["changed"]
                else _record()
            )
            return BuildiumApiFetchResult(
                records=[record], mode="sandbox", request_count=1
            )

        monkeypatch.setattr(api, "fetch_work_orders", fetched)
        reviewed = api.api_dry_run_buildium_work_orders(
            run.id,
            BuildiumApiWorkOrderDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        state["changed"] = True

        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_work_orders(
                run.id,
                BuildiumApiWorkOrderCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "WORK_ORDERS")
            .count()
            == 0
        )
        assert db.query(WorkOrder).count() == 1
        assert db.query(GLTransaction).count() == 0

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/work-orders/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/work-orders/api-commit"
            in paths
        )

        monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
        monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
        monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "work-order-secret")
        monkeypatch.setattr(
            transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
        )
        status = api.get_buildium_transport_status(current_user=admin)
        assert "WORK_ORDERS" in status.supported_resources
    finally:
        db.close()
        engine.dispose()
