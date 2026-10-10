"""Operational Commercial CAM/NNN posting must stay source-authorized and balanced."""
from __future__ import annotations

from datetime import date
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
from app.models.commercial_operating_charge import CommercialOperatingCharge
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs, commercial_lease_abstracts as abstracts
from app.routers import commercial_operating_charges as api
from app.schemas.commercial_operating_charge import (
    CommercialOperatingChargeIssueIn, CommercialOperatingChargeReverseIn,
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
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Commercial Ops", slug="commercial-ops")
    db.add(org); db.flush()
    admin = User(
        organization_id=org.id, role=UserRole.ADMIN,
        first_name="Ops", last_name="Admin", email="commercial-ops-admin@example.com",
        hashed_password="x", is_active=True,
    )
    manager = User(
        organization_id=org.id, role=UserRole.MANAGER,
        first_name="Ops", last_name="Manager", email="commercial-ops-manager@example.com",
        hashed_password="x", is_active=True,
    )
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT,
        first_name="Ops", last_name="Tenant", email="commercial-ops-tenant@example.com",
        hashed_password="x", is_active=True,
    )
    db.add_all((admin, manager, tenant)); db.flush()
    prop = Property(
        organization_id=org.id, name="Commercial Ops Property",
        property_type=PropertyType.COMMERCIAL, address_line1="1 Commerce",
        city="Cleveland", state="OH", zip_code="44113", is_active=True,
    )
    db.add(prop); db.flush()
    unit = Unit(property_id=prop.id, unit_number="C-1", monthly_rent=Decimal("2500"), is_active=True)
    db.add(unit); db.flush()
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id,
        start_date=date(2026, 1, 1), end_date=date(2028, 12, 31),
        monthly_rent=Decimal("2500"), security_deposit=Decimal("0"),
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease); db.flush()
    source = EntityAttachment(
        organization_id=org.id, entity_type="leases", entity_id=lease.id,
        storage_key="commercial-ops/source.pdf", original_name="source.pdf",
        content_type="application/pdf", size_bytes=100,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    db.add(source); db.flush()
    abstract = CommercialLeaseAbstract(
        organization_id=org.id, property_id=prop.id, lease_id=lease.id,
        source_attachment_id=source.id, rent_commencement_on=date(2026, 2, 1),
        created_by_id=admin.id, updated_by_id=admin.id, is_active=True,
    )
    db.add(abstract); db.flush()
    terms = CommercialLeaseTerms(
        organization_id=org.id, property_id=prop.id, lease_id=lease.id,
        abstract_id=abstract.id, source_attachment_id=source.id,
        revision=1, effective_on=date(2026, 2, 1),
        base_rent_monthly=Decimal("2500.00"),
        cam_estimate_monthly=Decimal("300.00"),
        property_tax_estimate_monthly=Decimal("125.00"),
        insurance_estimate_monthly=Decimal("75.00"),
        cam_share_percent=Decimal("12.5000"),
        billing_authorized_at=__import__("datetime").datetime.utcnow(),
        billing_authorized_by_id=admin.id,
        billing_authorization_note="Approved internally from private lease source.",
        is_active=True, created_by_id=admin.id,
    )
    db.add(terms)
    ar = GLAccount(
        organization_id=org.id, gl_number="1200", name="Tenant receivable",
        account_type="ASSET", is_active=True,
    )
    income = GLAccount(
        organization_id=org.id, gl_number="4300", name="Commercial recoveries",
        account_type="INCOME", is_active=True,
    )
    db.add_all((ar, income)); db.commit()
    return org, admin, manager, tenant, prop, unit, lease, source, abstract, terms, ar, income


def _payload(ar, income, *, kind="CAM", key="commercial-cam-2026-03", posting=date(2026, 3, 1)):
    return CommercialOperatingChargeIssueIn(
        kind=kind, period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
        posting_on=posting, due_on=date(2026, 3, 10),
        receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
        request_key=key,
    )


def test_cam_and_nnn_post_balanced_tenant_charges_and_reverse():
    db, engine = _db()
    try:
        org, admin, manager, tenant, prop, unit, lease, source, abstract, terms, ar, income = _seed(db)
        cam = api.issue_operating_charge(
            prop.id, abstract.id, _payload(ar, income),
            db=db, current_user=admin,
        )
        assert cam.kind == "CAM"
        assert cam.cam_amount == Decimal("300.00")
        assert cam.tax_amount == cam.insurance_amount == Decimal("0.00")
        assert cam.total_amount == Decimal("300.00")
        tenant_charge = db.get(Charge, cam.charge_id)
        assert tenant_charge.tenant_user_id == tenant.id
        assert tenant_charge.amount == Decimal("300.00")
        entries = db.query(GLEntry).filter(GLEntry.transaction_id == cam.gl_transaction_id).all()
        assert len(entries) == 2
        assert sum((row.debit for row in entries), Decimal("0")) == Decimal("300.00")
        assert sum((row.credit for row in entries), Decimal("0")) == Decimal("300.00")

        replay = api.issue_operating_charge(
            prop.id, abstract.id, _payload(ar, income),
            db=db, current_user=admin,
        )
        assert replay.id == cam.id
        nnn = api.issue_operating_charge(
            prop.id, abstract.id,
            _payload(ar, income, kind="NNN", key="commercial-nnn-2026-03"),
            db=db, current_user=admin,
        )
        assert nnn.cam_amount == Decimal("300.00")
        assert nnn.tax_amount == Decimal("125.00")
        assert nnn.insurance_amount == Decimal("75.00")
        assert nnn.total_amount == Decimal("500.00")
        response = Response()
        assert [row.id for row in api.list_operating_charges(
            prop.id, abstract.id, response, db=db, current_user=admin,
        )] == [nnn.id, cam.id]
        assert response.headers["cache-control"] == "no-store"

        reversed_row = api.reverse_operating_charge(
            prop.id, abstract.id, cam.id,
            CommercialOperatingChargeReverseIn(
                reversal_on=date(2026, 3, 2), reason="Duplicate CAM posting",
            ),
            db=db, current_user=admin,
        )
        assert reversed_row.status == "REVERSED"
        assert reversed_row.reversal_transaction_id is not None
        assert db.get(GLTransaction, cam.gl_transaction_id).is_reversed is True
        assert db.get(Charge, cam.charge_id).is_active is False
        assert api.reverse_operating_charge(
            prop.id, abstract.id, cam.id,
            CommercialOperatingChargeReverseIn(
                reversal_on=date(2026, 3, 2), reason="Duplicate CAM posting",
            ),
            db=db, current_user=admin,
        ).id == cam.id
        assert db.query(RentInvoice).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_operating_charge_requires_current_authorized_terms_and_valid_accounts(monkeypatch):
    db, engine = _db()
    try:
        org, admin, manager, tenant, prop, unit, lease, source, abstract, terms, ar, income = _seed(db)
        terms.billing_authorized_at = None
        terms.billing_authorized_by_id = None
        db.flush()
        with pytest.raises(HTTPException) as unauthorized:
            api.issue_operating_charge(
                prop.id, abstract.id, _payload(ar, income),
                db=db, current_user=admin,
            )
        assert unauthorized.value.status_code == 409
        terms.billing_authorized_at = __import__("datetime").datetime.utcnow()
        terms.billing_authorized_by_id = admin.id
        db.flush()
        with pytest.raises(HTTPException) as role_denied:
            api.issue_operating_charge(
                prop.id, abstract.id, _payload(ar, income),
                db=db, current_user=manager,
            )
        assert role_denied.value.status_code in {403, 404}
        with pytest.raises(HTTPException) as bad_account:
            api.issue_operating_charge(
                prop.id, abstract.id,
                _payload(income, ar, key="commercial-bad-accounts"),
                db=db, current_user=admin,
            )
        assert bad_account.value.status_code in {404, 422}
        terms.effective_on = date(2026, 4, 1)
        db.flush()
        with pytest.raises(HTTPException) as stale:
            api.issue_operating_charge(
                prop.id, abstract.id,
                _payload(ar, income, key="commercial-stale-terms"),
                db=db, current_user=admin,
            )
        assert stale.value.status_code == 409
        assert db.query(CommercialOperatingCharge).count() == 0
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_closed_period_and_paid_charge_block_reversal():
    db, engine = _db()
    try:
        org, admin, manager, tenant, prop, unit, lease, source, abstract, terms, ar, income = _seed(db)
        org.locked_through_date = date(2026, 3, 1)
        db.flush()
        with pytest.raises(HTTPException) as locked:
            api.issue_operating_charge(
                prop.id, abstract.id, _payload(ar, income),
                db=db, current_user=admin,
            )
        assert locked.value.status_code == 409
        db.rollback()
        org = db.query(Organization).filter(Organization.slug == "commercial-ops").one()
        org.locked_through_date = None
        db.flush()
        # Re-fetch scoped rows after rollback.
        admin = db.query(User).filter(User.email == "commercial-ops-admin@example.com").one()
        prop = db.query(Property).filter(Property.name == "Commercial Ops Property").one()
        abstract = db.query(CommercialLeaseAbstract).filter(
            CommercialLeaseAbstract.property_id == prop.id,
        ).one()
        ar = db.query(GLAccount).filter(GLAccount.gl_number == "1200").one()
        income = db.query(GLAccount).filter(GLAccount.gl_number == "4300").one()
        row = api.issue_operating_charge(
            prop.id, abstract.id, _payload(ar, income),
            db=db, current_user=admin,
        )
        charge = db.get(Charge, row.charge_id)
        charge.amount_paid = Decimal("1.00")
        db.commit()
        with pytest.raises(HTTPException) as paid:
            api.reverse_operating_charge(
                prop.id, abstract.id, row.id,
                CommercialOperatingChargeReverseIn(
                    reversal_on=date(2026, 3, 2), reason="Cannot reverse paid",
                ),
                db=db, current_user=admin,
            )
        assert paid.value.status_code == 409
    finally:
        db.rollback(); db.close(); engine.dispose()
