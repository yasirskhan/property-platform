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
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization
from app.models.vendor import Vendor
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiBillCommitIn,
    BuildiumApiBillDryRunIn,
    BuildiumBillResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-api-bill-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Bill",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Bill Target",
        slug="buildium-api-bill-target",
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
        "Id": 9001,
        "Date": "2026-09-30",
        "DueDate": "2026-10-15",
        "PaidDate": None,
        "Memo": "DO-NOT-PERSIST-PRIVATE-BILL-MEMO",
        "VendorId": 4001,
        "WorkOrderId": None,
        "ReferenceNumber": "INV-9001",
        "ApprovalStatus": "NotNeeded",
        "Lines": [
            {
                "Id": 9101,
                "AccountingEntity": {
                    "Id": 1001,
                    "AccountingEntityType": "Rental",
                    "Unit": {"Id": 2001},
                },
                "GLAccount": {
                    "Id": 7001,
                    "AccountNumber": "6852",
                    "Name": "Plumbing",
                    "Description": "DO-NOT-PERSIST-PRIVATE-GL-DESCRIPTION",
                    "Type": "Expense",
                    "SubType": "RepairsAndMaintenance",
                },
                "Amount": 275.50,
                "Markup": {"Amount": 0, "Type": "Percent"},
                "Memo": "DO-NOT-PERSIST-PRIVATE-LINE-MEMO",
            }
        ],
    }
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="API Bill Property",
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
    expense = GLAccount(
        organization_id=run.organization_id,
        gl_number="6852",
        name="Plumbing",
        account_type="EXPENSE",
        is_active=True,
    )
    payable = GLAccount(
        organization_id=run.organization_id,
        gl_number="2100",
        name="Accounts Payable",
        account_type="LIABILITY",
        is_active=True,
    )
    db.add_all([unit, vendor, expense, payable])
    db.flush()

    bill = Bill(
        organization_id=run.organization_id,
        bill_number="B-9001",
        payee_name=vendor.company_name,
        vendor_id=vendor.id,
        bill_date=date(2026, 9, 30),
        due_date=date(2026, 10, 15),
        reference_number="INV-9001",
        amount=Decimal("275.50"),
        amount_paid=Decimal("0.00"),
        status="UNPAID",
        property_id=prop.id,
        unit_id=unit.id,
        payable_gl_account_id=payable.id,
        is_reversed=False,
        is_active=True,
    )
    db.add(bill)
    db.flush()
    db.add(
        BillLine(
            organization_id=run.organization_id,
            bill_id=bill.id,
            gl_account_id=expense.id,
            property_id=prop.id,
            unit_id=unit.id,
            description="Existing local plumbing line",
            amount=Decimal("275.50"),
        )
    )

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
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="GL_ACCOUNTS",
                source_id="7001",
                target_entity="GL_ACCOUNT",
                target_id=expense.id,
                source_fingerprint="g" * 64,
            ),
        ]
    )
    db.commit()
    return bill


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_buildium_transport_fetches_bills_from_fixed_endpoint(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "bill-secret")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_record()])

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_bills(expected_source_account_ref="sandbox-account-A")
    assert result.records[0]["Id"] == 9001
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/bills"
    assert calls[0][1]["x-buildium-client-secret"] == "bill-secret"
    assert calls[0][2] == {"offset": 0, "limit": 500}


def test_buildium_api_bill_maps_existing_relationship_only_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        target = _target(db, run)
        original = {
            "amount": target.amount,
            "amount_paid": target.amount_paid,
            "status": target.status,
            "payable_gl_account_id": target.payable_gl_account_id,
            "gl_transaction_id": target.gl_transaction_id,
            "line_count": len(target.lines),
        }

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_record()], mode="sandbox", request_count=1
            )

        monkeypatch.setattr(api, "fetch_bills", fetched)
        resolution = BuildiumBillResolutionIn(
            source_id=9001,
            action="MATCH_EXISTING",
            target_bill_id=target.id,
        )
        reviewed = api.api_dry_run_buildium_bills(
            run.id,
            BuildiumApiBillDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.rows[0].mapped["amount"] == "275.50"

        committed = api.api_commit_buildium_bills(
            run.id,
            BuildiumApiBillCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "BILLS")
            .one()
        )
        assert mapping.target_entity == "BILL_RELATIONSHIP"
        assert mapping.target_id == target.id
        assert db.query(Bill).count() == 1
        assert db.query(BillLine).count() == 1
        assert db.query(GLTransaction).count() == 0

        db.refresh(target)
        assert target.amount == original["amount"]
        assert target.amount_paid == original["amount_paid"]
        assert target.status == original["status"]
        assert target.payable_gl_account_id == original["payable_gl_account_id"]
        assert target.gl_transaction_id == original["gl_transaction_id"]
        assert len(target.lines) == original["line_count"]

        with pytest.raises(ValidationError):
            BuildiumApiBillDryRunIn(client_secret="secret")
        with pytest.raises(ValidationError):
            BuildiumApiBillCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
            )

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-PRIVATE-BILL-MEMO" not in audit
        assert "DO-NOT-PERSIST-PRIVATE-GL-DESCRIPTION" not in audit
        assert "DO-NOT-PERSIST-PRIVATE-LINE-MEMO" not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_bill_commit_refetch_detects_drift_and_routes_exist(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        target = _target(db, run)
        resolution = BuildiumBillResolutionIn(
            source_id=9001,
            action="MATCH_EXISTING",
            target_bill_id=target.id,
        )
        state = {"changed": False}

        def fetched(*, expected_source_account_ref):
            record = (
                _record(ReferenceNumber="INV-CHANGED")
                if state["changed"]
                else _record()
            )
            return BuildiumApiFetchResult(
                records=[record], mode="sandbox", request_count=1
            )

        monkeypatch.setattr(api, "fetch_bills", fetched)
        reviewed = api.api_dry_run_buildium_bills(
            run.id,
            BuildiumApiBillDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        state["changed"] = True
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_bills(
                run.id,
                BuildiumApiBillCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "BILLS")
            .count()
            == 0
        )
        assert db.query(Bill).count() == 1
        assert db.query(BillLine).count() == 1
        assert db.query(GLTransaction).count() == 0

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/bills/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/bills/api-commit"
            in paths
        )

        monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
        monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
        monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "bill-secret")
        monkeypatch.setattr(
            transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
        )
        status = api.get_buildium_transport_status(current_user=admin)
        assert "BILLS" in status.supported_resources
    finally:
        db.close()
        engine.dispose()
