from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, Unit
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.user import Organization, User, UserRole
from app.routers import buildium_lease_payment_migrations as api
from app.schemas.buildium_lease_payment_migration import (
    BuildiumLeasePaymentCommitIn,
    BuildiumLeasePaymentDryRunIn,
    BuildiumLeasePaymentResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_admin(db):
    row = PlatformUser(
        email="buildium-payment-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Admin",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(name="Buildium Payment Org", slug="buildium-payment-org", is_active=True)
    db.add(org)
    db.flush()
    tenant = User(
        email="tenant-buildium-payment@example.com",
        hashed_password=hash_password("tenant-password"),
        first_name="Lease",
        last_name="Tenant",
        role=UserRole.TENANT,
        organization_id=org.id,
        is_active=True,
    )
    db.add(tenant)
    db.flush()
    prop = Property(
        organization_id=org.id,
        name="Mapped Property",
        address_line1="10 Lake Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add(prop)
    db.flush()
    unit = Unit(
        property_id=prop.id,
        unit_number="1A",
        monthly_rent=Decimal("1000.00"),
        is_active=True,
    )
    db.add(unit)
    db.flush()
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=Decimal("1000.00"),
        security_deposit=Decimal("0.00"),
        due_day=1,
        status=LeaseStatus.ACTIVE,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Rental Trust",
        account_type="ASSET",
        is_active=True,
    )
    income = GLAccount(
        organization_id=org.id,
        gl_number="4100",
        name="Rental Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add_all([lease, cash, income])
    db.flush()

    receipt = Receipt(
        organization_id=org.id,
        type="TENANT",
        receipt_date=date(2026, 10, 1),
        amount=Decimal("1000.00"),
        cash_gl_account_id=cash.id,
        tenant_user_id=tenant.id,
        property_id=prop.id,
        unit_id=unit.id,
        reference_number="CHK-55",
        is_reversed=False,
        is_active=True,
    )
    db.add(receipt)
    db.flush()
    line = ReceiptLine(
        organization_id=org.id,
        receipt_id=receipt.id,
        gl_account_id=income.id,
        property_id=prop.id,
        unit_id=unit.id,
        description="Rent",
        amount_to_pay=Decimal("1000.00"),
        line_date=date(2026, 10, 1),
        is_prepayment=False,
    )
    db.add(line)
    db.flush()
    txn = GLTransaction(
        organization_id=org.id,
        transaction_date=date(2026, 10, 1),
        transaction_type="RECEIPT",
        reference_number="CHK-55",
        memo="Rent payment",
        source_type="receipt",
        source_id=receipt.id,
        is_reversed=False,
    )
    db.add(txn)
    db.flush()
    db.add_all([
        GLEntry(
            organization_id=org.id,
            transaction_id=txn.id,
            gl_account_id=cash.id,
            property_id=prop.id,
            unit_id=unit.id,
            debit=Decimal("1000.00"),
            credit=Decimal("0.00"),
        ),
        GLEntry(
            organization_id=org.id,
            transaction_id=txn.id,
            gl_account_id=income.id,
            property_id=prop.id,
            unit_id=unit.id,
            debit=Decimal("0.00"),
            credit=Decimal("1000.00"),
        ),
    ])
    receipt.gl_transaction_id = txn.id

    run = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-payment-source",
        status="DRAFT",
    )
    db.add(run)
    db.flush()

    mappings = [
        ("PROPERTIES", "1001", "PROPERTY", prop.id),
        ("UNITS", "2001", "UNIT", unit.id),
        ("TENANTS", "3001", "TENANT_USER", tenant.id),
        ("LEASES", "4001", "LEASE_RELATIONSHIP", lease.id),
        ("GL_ACCOUNTS", "5001", "GL_ACCOUNT", cash.id),
        ("GL_ACCOUNTS", "5002", "GL_ACCOUNT", income.id),
    ]
    for index, (resource, source_id, entity, target_id) in enumerate(mappings, start=1):
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=org.id,
                provider="BUILDIUM",
                resource=resource,
                source_id=source_id,
                target_entity=entity,
                target_id=target_id,
                source_fingerprint=f"{index:x}" * 64,
            )
        )
    db.commit()
    return org, tenant, prop, unit, lease, cash, income, receipt, run


def _record():
    return {
        "Id": 9001,
        "LeaseId": 4001,
        "Date": "2026-10-01",
        "TransactionTypeEnum": "Payment",
        "TransactionType": "Payment",
        "TotalAmount": 1000,
        "CheckNumber": "CHK-55",
        "PaymentDetail": {
            "PaymentMethod": "Check",
            "Payee": {"Id": 3001, "Name": "Lease Tenant", "Type": "Tenant"},
            "IsInternalTransaction": False,
            "InternalTransactionStatus": {"IsPending": False},
        },
        "Journal": {
            "Memo": "Rent payment",
            "Lines": [
                {
                    "GLAccount": {"Id": 5001},
                    "Amount": 1000,
                    "IsCashPosting": True,
                    "ReferenceNumber": "CHK-55",
                    "AccountingEntity": {
                        "Id": 1001,
                        "AccountingEntityType": "Rental",
                        "Unit": {"Id": 2001},
                    },
                },
                {
                    "GLAccount": {"Id": 5002},
                    "Amount": 1000,
                    "IsCashPosting": False,
                    "ReferenceNumber": "CHK-55",
                    "AccountingEntity": {
                        "Id": 1001,
                        "AccountingEntityType": "Rental",
                        "Unit": {"Id": 2001},
                    },
                },
            ],
        },
    }


def test_buildium_lease_payment_reconciles_existing_receipt_and_replays_without_money_mutation():
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org, tenant, prop, unit, lease, cash, income, receipt, run = _fixture(db)
        before = {
            "receipts": db.query(Receipt).count(),
            "lines": db.query(ReceiptLine).count(),
            "txns": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        }

        preview = api.dry_run_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.total == 1
        assert preview.reviewable == 1
        assert preview.invalid == 0
        assert preview.rows[0].resolution_action is None
        assert any("Possible exact existing target Receipt" in item for item in preview.rows[0].warnings)

        resolution = BuildiumLeasePaymentResolutionIn(
            source_id=9001,
            action="MATCH_EXISTING",
            target_receipt_id=receipt.id,
        )
        reviewed = api.dry_run_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        assert committed.rows[0].target_receipt_id == receipt.id
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.resource == "LEASE_PAYMENTS",
                PlatformMigrationItem.source_id == "9001",
            )
            .one()
        )
        assert mapping.target_entity == "RECEIPT_RELATIONSHIP"
        assert mapping.target_id == receipt.id

        replay_preview = api.dry_run_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASE_PAYMENTS"
        ).count() == 1
        after = {
            "receipts": db.query(Receipt).count(),
            "lines": db.query(ReceiptLine).count(),
            "txns": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        }
        assert after == before
    finally:
        db.close()
        engine.dispose()


def test_buildium_lease_payment_fails_closed_for_pending_or_receipt_gl_drift():
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org, tenant, prop, unit, lease, cash, income, receipt, run = _fixture(db)

        pending = _record()
        pending["PaymentDetail"]["InternalTransactionStatus"]["IsPending"] = True
        result = api.dry_run_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentDryRunIn(records=[pending]),
            db=db,
            current_user=admin,
        )
        assert result.invalid == 1
        assert "Pending Buildium internal payment" in result.rows[0].reason

        source = _record()
        resolution = BuildiumLeasePaymentResolutionIn(
            source_id=9001,
            action="MATCH_EXISTING",
            target_receipt_id=receipt.id,
        )
        reviewed = api.dry_run_buildium_lease_payments(
            run.id,
            BuildiumLeasePaymentDryRunIn(records=[source], resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        credit_entry = (
            db.query(GLEntry)
            .filter(
                GLEntry.transaction_id == receipt.gl_transaction_id,
                GLEntry.gl_account_id == income.id,
            )
            .one()
        )
        credit_entry.credit = Decimal("999.00")
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_lease_payments(
                run.id,
                BuildiumLeasePaymentCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[source],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASE_PAYMENTS"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_lease_payment_routes_are_exposed():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/platform/migrations/buildium/runs/{run_id}/lease-payments/dry-run" in paths
    assert "/api/platform/migrations/buildium/runs/{run_id}/lease-payments/commit" in paths
