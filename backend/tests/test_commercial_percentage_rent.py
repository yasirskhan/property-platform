"""Operational percentage rent must use current source-backed terms and balanced GL."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.charge import Charge
from app.models.commercial_lease_abstract import CommercialLeaseAbstract, CommercialLeaseTerms
from app.models.commercial_percentage_rent import CommercialPercentageRentCharge
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs, commercial_lease_abstracts as abstracts
from app.routers import commercial_operating_charges as operating
from app.routers import commercial_percentage_rent as api
from app.schemas.commercial_percentage_rent import (
    CommercialPercentageRentIn, CommercialPercentageRentReverseIn,
)


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
    monkeypatch.setattr(affordable_programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(affordable_programs, "resolve_customer_features",
                        lambda *a, **k: [SimpleNamespace(
                            key=affordable_programs.FEATURE_KEY, allowed=True,
                        )])
    monkeypatch.setattr(abstracts, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(abstracts, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=abstracts.ATTACHMENTS_FEATURE_KEY, allowed=True),
    ])
    monkeypatch.setattr(operating, "permission_allows_user", lambda *a, **k: True)


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Commercial Percentage", slug="commercial-percentage")
    db.add(org); db.flush()
    admin = User(
        organization_id=org.id, role=UserRole.ADMIN,
        first_name="Pct", last_name="Admin", email="pct-admin@example.com",
        hashed_password="x", is_active=True,
    )
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT,
        first_name="Pct", last_name="Tenant", email="pct-tenant@example.com",
        hashed_password="x", is_active=True,
    )
    db.add_all((admin, tenant)); db.flush()
    prop = Property(
        organization_id=org.id, name="Percentage Retail",
        property_type=PropertyType.COMMERCIAL, address_line1="8 Retail",
        city="Cleveland", state="OH", zip_code="44113", is_active=True,
    )
    db.add(prop); db.flush()
    unit = Unit(property_id=prop.id, unit_number="P-1", monthly_rent=Decimal("4000"), is_active=True)
    db.add(unit); db.flush()
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id,
        start_date=date(2025, 1, 1), end_date=date(2028, 12, 31),
        monthly_rent=Decimal("4000"), security_deposit=Decimal("0"),
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease); db.flush()
    source = EntityAttachment(
        organization_id=org.id, entity_type="leases", entity_id=lease.id,
        storage_key="percentage/source.pdf", original_name="lease-source.pdf",
        content_type="application/pdf", size_bytes=100,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    sales = EntityAttachment(
        organization_id=org.id, entity_type="leases", entity_id=lease.id,
        storage_key="percentage/sales.pdf", original_name="tenant-sales-2026.pdf",
        content_type="application/pdf", size_bytes=100,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    db.add_all((source, sales)); db.flush()
    abstract = CommercialLeaseAbstract(
        organization_id=org.id, property_id=prop.id, lease_id=lease.id,
        source_attachment_id=source.id, rent_commencement_on=date(2025, 1, 1),
        created_by_id=admin.id, updated_by_id=admin.id, is_active=True,
    )
    db.add(abstract); db.flush()
    terms = CommercialLeaseTerms(
        organization_id=org.id, property_id=prop.id, lease_id=lease.id,
        abstract_id=abstract.id, source_attachment_id=source.id,
        revision=1, effective_on=date(2025, 1, 1),
        percentage_rent_rate=Decimal("5.0000"),
        percentage_rent_breakpoint_annual=Decimal("500000.00"),
        cam_estimate_monthly=Decimal("0.00"),
        property_tax_estimate_monthly=Decimal("0.00"),
        insurance_estimate_monthly=Decimal("0.00"),
        billing_authorized_at=datetime.utcnow(),
        billing_authorized_by_id=admin.id,
        billing_authorization_note="Approved from source.",
        is_active=True, created_by_id=admin.id,
    )
    db.add(terms)
    ar = GLAccount(
        organization_id=org.id, gl_number="1210", name="Commercial receivable",
        account_type="ASSET", is_active=True,
    )
    income = GLAccount(
        organization_id=org.id, gl_number="4310", name="Percentage rent income",
        account_type="INCOME", is_active=True,
    )
    db.add_all((ar, income)); db.commit()
    return org, admin, tenant, prop, unit, lease, source, sales, abstract, terms, ar, income


def _payload(sales, ar, income, *, gross="600000.00", year=2026, key="percentage-rent-2026"):
    return CommercialPercentageRentIn(
        reporting_year=year,
        evidence_attachment_id=sales.id,
        gross_sales=Decimal(gross),
        posting_on=date(2026, 9, 30),
        due_on=date(2026, 10, 15),
        receivable_gl_account_id=ar.id,
        income_gl_account_id=income.id,
        request_key=key,
    )


def test_percentage_rent_posts_excess_only_and_reverses_unpaid():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, source, sales, abstract, terms, ar, income = _seed(db)
        row = api.record_percentage_rent(
            prop.id, abstract.id, _payload(sales, ar, income),
            db=db, current_user=admin,
        )
        assert row.gross_sales == Decimal("600000.00")
        assert row.breakpoint_annual == Decimal("500000.00")
        assert row.excess_sales == Decimal("100000.00")
        assert row.rate_percent == Decimal("5.0000")
        assert row.percentage_rent_due == Decimal("5000.00")
        assert row.status == "POSTED"
        charge = db.get(Charge, row.charge_id)
        assert charge.tenant_user_id == tenant.id
        assert charge.amount == Decimal("5000.00")
        entries = db.query(GLEntry).filter(GLEntry.transaction_id == row.gl_transaction_id).all()
        assert len(entries) == 2
        assert sum((e.debit for e in entries), Decimal("0")) == Decimal("5000.00")
        assert sum((e.credit for e in entries), Decimal("0")) == Decimal("5000.00")
        response = Response()
        assert [x.id for x in api.list_percentage_rent(
            prop.id, abstract.id, response, db=db, current_user=admin,
        )] == [row.id]
        assert response.headers["cache-control"] == "no-store"
        assert api.record_percentage_rent(
            prop.id, abstract.id, _payload(sales, ar, income),
            db=db, current_user=admin,
        ).id == row.id

        reversed_row = api.reverse_percentage_rent(
            prop.id, abstract.id, row.id,
            CommercialPercentageRentReverseIn(
                reversal_on=date(2026, 10, 1), reason="Correct tenant sales evidence",
            ),
            db=db, current_user=admin,
        )
        assert reversed_row.status == "REVERSED"
        assert reversed_row.reversal_transaction_id is not None
        assert db.get(GLTransaction, row.gl_transaction_id).is_reversed is True
        assert db.get(Charge, row.charge_id).is_active is False
        assert db.query(RentInvoice).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_percentage_rent_zero_below_breakpoint_has_no_money():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, source, sales, abstract, terms, ar, income = _seed(db)
        row = api.record_percentage_rent(
            prop.id, abstract.id,
            _payload(sales, ar, income, gross="450000.00"),
            db=db, current_user=admin,
        )
        assert row.status == "ZERO"
        assert row.excess_sales == row.percentage_rent_due == Decimal("0.00")
        assert row.charge_id is row.gl_transaction_id is None
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        with pytest.raises(HTTPException) as reverse:
            api.reverse_percentage_rent(
                prop.id, abstract.id, row.id,
                CommercialPercentageRentReverseIn(
                    reversal_on=date(2026, 10, 1), reason="No posting exists",
                ),
                db=db, current_user=admin,
            )
        assert reverse.value.status_code == 409
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_percentage_rent_requires_current_terms_private_evidence_and_unique_year():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, source, sales, abstract, terms, ar, income = _seed(db)
        shared = EntityAttachment(
            organization_id=org.id, entity_type="leases", entity_id=lease.id,
            storage_key="percentage/shared.pdf", original_name="shared.pdf",
            content_type="application/pdf", size_bytes=10,
            share_with_tenants=True, share_with_owners=False,
            uploaded_by_id=admin.id, is_active=True,
        )
        db.add(shared); db.commit()
        bad = _payload(sales, ar, income, key="percentage-bad-evidence")
        bad.evidence_attachment_id = shared.id
        with pytest.raises(HTTPException) as evidence:
            api.record_percentage_rent(prop.id, abstract.id, bad, db=db, current_user=admin)
        assert evidence.value.status_code == 404

        terms.percentage_rent_rate = None
        db.flush()
        with pytest.raises(HTTPException) as missing:
            api.record_percentage_rent(
                prop.id, abstract.id,
                _payload(sales, ar, income, key="percentage-missing-terms"),
                db=db, current_user=admin,
            )
        assert missing.value.status_code == 409
        terms.percentage_rent_rate = Decimal("5.0000")
        db.flush()

        first = api.record_percentage_rent(
            prop.id, abstract.id, _payload(sales, ar, income),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as duplicate:
            api.record_percentage_rent(
                prop.id, abstract.id,
                _payload(sales, ar, income, gross="610000.00", key="percentage-other-key"),
                db=db, current_user=admin,
            )
        assert duplicate.value.status_code == 409
        db.get(Charge, first.charge_id).amount_paid = Decimal("1.00")
        db.commit()
        with pytest.raises(HTTPException) as paid:
            api.reverse_percentage_rent(
                prop.id, abstract.id, first.id,
                CommercialPercentageRentReverseIn(
                    reversal_on=date(2026, 10, 1), reason="Cannot reverse paid",
                ),
                db=db, current_user=admin,
            )
        assert paid.value.status_code == 409
    finally:
        db.rollback(); db.close(); engine.dispose()
