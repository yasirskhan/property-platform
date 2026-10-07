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
from app.models.bank_account import BankAccount
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.check import Check
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiBillPaymentCommitIn,
    BuildiumApiBillPaymentDryRunIn,
    BuildiumBillPaymentResolutionIn,
)
from app.schemas.check import CheckAllocationIn, CheckIssueIn
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import (
    BuildiumApiFetchResult,
    BuildiumApiTransportError,
)
from app.services.checks import issue_check


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_admin(db):
    row = PlatformUser(
        email="buildium-api-bill-payment-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="BillPayment",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Bill Payment Target",
        slug="buildium-api-bill-payment-target",
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
        "Id": 11001,
        "BankAccountId": 10001,
        "EntryDate": "2026-09-20",
        "Memo": "DO-NOT-PERSIST-PROVIDER-PAYMENT-MEMO",
        "CheckNumber": "1042",
        "PaidBillIds": [9001],
        "AppliedVendorCredits": [],
        "Lines": [
            {
                "AccountingEntity": {
                    "Id": 1001,
                    "AccountingEntityType": "Rental",
                    "UnitId": 2001,
                },
                "GLAccountId": 7001,
                "Amount": 125.50,
            }
        ],
    }
    row.update(changes)
    return row


def _api_record(**changes):
    row = _provider_record()
    row["_ParentBillId"] = 9001
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="Bill Payment Property",
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
    cash = GLAccount(
        organization_id=run.organization_id,
        gl_number="1100",
        name="Operating Cash",
        account_type="ASSET",
        is_active=True,
    )
    db.add_all([unit, expense, payable, cash])
    db.flush()
    bank = BankAccount(
        organization_id=run.organization_id,
        name="Local Operating",
        bank_name="DO-NOT-PERSIST-LOCAL-BANK",
        routing_number="DO-NOT-PERSIST-LOCAL-ROUTING",
        account_number="DO-NOT-PERSIST-LOCAL-ACCOUNT",
        gl_account_id=cash.id,
        account_type="OPERATING",
        is_active=True,
    )
    db.add(bank)
    db.flush()
    bill = Bill(
        organization_id=run.organization_id,
        bill_number="B-9001",
        payee_name="API Plumbing Vendor",
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 20),
        reference_number="INV-9001",
        amount=Decimal("125.50"),
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
            amount=Decimal("125.50"),
        )
    )
    for resource, source_id, target_entity, target_id, fingerprint in (
        ("PROPERTIES", "1001", "PROPERTY", prop.id, "p" * 64),
        ("UNITS", "2001", "UNIT", unit.id, "u" * 64),
        ("GL_ACCOUNTS", "7001", "GL_ACCOUNT", expense.id, "g" * 64),
        ("BILLS", "9001", "BILL_RELATIONSHIP", bill.id, "b" * 64),
        ("BANK_ACCOUNTS", "10001", "BANK_ACCOUNT", bank.id, "k" * 64),
    ):
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource=resource,
                source_id=source_id,
                target_entity=target_entity,
                target_id=target_id,
                source_fingerprint=fingerprint,
            )
        )
    customer_admin = User(
        email="bill-payment-customer-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Customer",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=run.organization_id,
        is_active=True,
        is_verified=True,
    )
    db.add(customer_admin)
    db.commit()

    check = issue_check(
        db,
        organization_id=run.organization_id,
        payload=CheckIssueIn(
            bank_account_id=bank.id,
            check_date=date(2026, 9, 20),
            check_number="1042",
            memo="ORIGINAL-LOCAL-CHECK-MEMO",
            allocations=[CheckAllocationIn(bill_id=bill.id, amount=125.50)],
        ),
        created_by=customer_admin,
    )
    db.commit()
    db.refresh(bill)
    db.refresh(check)
    return bill, bank, check


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
        transport.settings, "BUILDIUM_API_CLIENT_SECRET", "bill-payment-secret"
    )
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )


def test_buildium_transport_fetches_nested_bill_payments_and_bounds_fanout(monkeypatch):
    _configure_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        if url.endswith("/v1/bills/9001/payments"):
            return _Response(200, [_provider_record()])
        if url.endswith("/v1/bills/9002/payments"):
            return _Response(200, [])
        raise AssertionError(url)

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_bill_payments(
        expected_source_account_ref="sandbox-account-A",
        parent_bill_ids=["9002", "9001"],
    )
    assert result.records[0]["Id"] == 11001
    assert result.records[0]["_ParentBillId"] == 9001
    assert result.parent_record_count == 2
    assert result.request_count == 2
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/bills/9001/payments"
    assert calls[0][2] == {"offset": 0, "limit": 501}
    assert calls[1][0] == "https://apisandbox.buildium.com/v1/bills/9002/payments"
    assert calls[0][1]["x-buildium-client-secret"] == "bill-payment-secret"

    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_bill_payments(
            expected_source_account_ref="sandbox-account-A",
            parent_bill_ids=list(
                range(1, transport.MAX_BILL_PAYMENT_PARENT_BILLS + 2)
            ),
        )
    assert exc.value.code == "source_too_large"

    def too_many(url, *, headers, params, timeout):
        return _Response(
            200,
            [
                _provider_record(Id=12000 + index)
                for index in range(transport.MAX_BILL_PAYMENT_RECORDS + 1)
            ],
        )

    monkeypatch.setattr(transport.requests, "get", too_many)
    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_bill_payments(
            expected_source_account_ref="sandbox-account-A",
            parent_bill_ids=[9001],
        )
    assert exc.value.code == "source_too_large"


def test_buildium_api_bill_payment_maps_existing_check_only_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        bill, bank, check = _target(db, run)
        gl_count = db.query(GLTransaction).count()

        def fetched(*, expected_source_account_ref, parent_bill_ids):
            assert expected_source_account_ref == "sandbox-account-A"
            assert parent_bill_ids == ["9001"]
            return BuildiumApiFetchResult(
                records=[_api_record()],
                mode="sandbox",
                request_count=1,
                parent_record_count=1,
            )

        monkeypatch.setattr(api, "fetch_bill_payments", fetched)
        resolution = BuildiumBillPaymentResolutionIn(
            source_id=11001,
            action="MATCH_EXISTING",
            target_check_id=check.id,
        )
        reviewed = api.api_dry_run_buildium_bill_payments(
            run.id,
            BuildiumApiBillPaymentDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.rows[0].mapped["parent_bill_source_id"] == "9001"
        assert reviewed.rows[0].mapped["target_bill_id"] == bill.id
        assert reviewed.rows[0].mapped["target_bank_account_id"] == bank.id

        committed = api.api_commit_buildium_bill_payments(
            run.id,
            BuildiumApiBillPaymentCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "BILL_PAYMENTS")
            .one()
        )
        assert mapping.target_entity == "CHECK_PAYMENT_RELATIONSHIP"
        assert mapping.target_id == check.id
        assert db.query(Check).count() == 1
        assert db.query(GLTransaction).count() == gl_count

        replay = api.api_commit_buildium_bill_payments(
            run.id,
            BuildiumApiBillPaymentCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.matched_existing == 1
        assert db.query(Check).count() == 1
        assert db.query(GLTransaction).count() == gl_count

        with pytest.raises(ValidationError):
            BuildiumApiBillPaymentDryRunIn(records=[_api_record()])
        with pytest.raises(ValidationError):
            BuildiumApiBillPaymentCommitIn(
                fingerprint=reviewed.fingerprint,
                client_secret="secret",
            )

        audit = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        for secret in (
            "DO-NOT-PERSIST-PROVIDER-PAYMENT-MEMO",
            "DO-NOT-PERSIST-LOCAL-BANK",
            "DO-NOT-PERSIST-LOCAL-ROUTING",
            "DO-NOT-PERSIST-LOCAL-ACCOUNT",
        ):
            assert secret not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()

        _configure_transport(monkeypatch)
        status = api.get_buildium_transport_status(current_user=admin)
        assert "BILL_PAYMENTS" in status.supported_resources
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_bill_payment_refetch_and_target_snapshot_fail_closed(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, _, check = _target(db, run)
        state = {"provider_memo": "ORIGINAL-PROVIDER-MEMO"}

        def fetched(*, expected_source_account_ref, parent_bill_ids):
            assert expected_source_account_ref == "sandbox-account-A"
            assert parent_bill_ids == ["9001"]
            return BuildiumApiFetchResult(
                records=[_api_record(Memo=state["provider_memo"])],
                mode="sandbox",
                request_count=1,
                parent_record_count=1,
            )

        monkeypatch.setattr(api, "fetch_bill_payments", fetched)
        resolution = BuildiumBillPaymentResolutionIn(
            source_id=11001,
            action="MATCH_EXISTING",
            target_check_id=check.id,
        )
        reviewed = api.api_dry_run_buildium_bill_payments(
            run.id,
            BuildiumApiBillPaymentDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )

        check.memo = "TARGET-CHECK-MEMO-CHANGED-AFTER-REVIEW"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_bill_payments(
                run.id,
                BuildiumApiBillPaymentCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "BILL_PAYMENTS")
            .count()
            == 0
        )

        check.memo = "ORIGINAL-LOCAL-CHECK-MEMO"
        db.commit()
        state["provider_memo"] = "PROVIDER-MEMO-CHANGED-AFTER-REVIEW"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_bill_payments(
                run.id,
                BuildiumApiBillPaymentCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        assert db.query(Check).count() == 1

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/bill-payments/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/bill-payments/api-commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_bill_payment_rejects_nested_parent_mismatch(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _target(db, run)

        def fetched(*, expected_source_account_ref, parent_bill_ids):
            assert expected_source_account_ref == "sandbox-account-A"
            assert parent_bill_ids == ["9001"]
            return BuildiumApiFetchResult(
                records=[_api_record(_ParentBillId=9999)],
                mode="sandbox",
                request_count=1,
                parent_record_count=1,
            )

        monkeypatch.setattr(api, "fetch_bill_payments", fetched)
        result = api.api_dry_run_buildium_bill_payments(
            run.id,
            BuildiumApiBillPaymentDryRunIn(),
            db=db,
            current_user=admin,
        )
        assert result.invalid == 1
        assert "nested parent Bill" in result.rows[0].reason
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "BILL_PAYMENTS")
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()
