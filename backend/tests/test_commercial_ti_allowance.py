"""Commercial TI allowance tracking must remain capped, source-backed, and non-financial."""
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
from app.models.commercial_ti_allowance import CommercialTIAllowanceUse
from app.models.entity_attachment import EntityAttachment
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs, commercial_lease_abstracts as abstracts
from app.routers import commercial_operating_charges as operating
from app.routers import commercial_ti_allowance as api
from app.schemas.commercial_ti_allowance import CommercialTIAllowanceUseIn, CommercialTIAllowanceVoidIn


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
    org = Organization(name="Commercial TI", slug="commercial-ti")
    db.add(org); db.flush()
    admin = User(
        organization_id=org.id, role=UserRole.ADMIN,
        first_name="TI", last_name="Admin", email="ti-admin@example.com",
        hashed_password="x", is_active=True,
    )
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT,
        first_name="TI", last_name="Tenant", email="ti-tenant@example.com",
        hashed_password="x", is_active=True,
    )
    db.add_all((admin, tenant)); db.flush()
    prop = Property(
        organization_id=org.id, name="TI Retail",
        property_type=PropertyType.COMMERCIAL, address_line1="9 Retail",
        city="Cleveland", state="OH", zip_code="44113", is_active=True,
    )
    db.add(prop); db.flush()
    unit = Unit(property_id=prop.id, unit_number="TI-1", monthly_rent=Decimal("4500"), is_active=True)
    db.add(unit); db.flush()
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id,
        start_date=date(2025, 1, 1), end_date=date(2028, 12, 31),
        monthly_rent=Decimal("4500"), security_deposit=Decimal("0"),
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease); db.flush()
    source = EntityAttachment(
        organization_id=org.id, entity_type="leases", entity_id=lease.id,
        storage_key="ti/source.pdf", original_name="lease-source.pdf",
        content_type="application/pdf", size_bytes=100,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    ti_evidence = EntityAttachment(
        organization_id=org.id, entity_type="leases", entity_id=lease.id,
        storage_key="ti/invoice.pdf", original_name="ti-invoice.pdf",
        content_type="application/pdf", size_bytes=100,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    db.add_all((source, ti_evidence)); db.flush()
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
        ti_allowance_total=Decimal("25000.00"),
        cam_estimate_monthly=Decimal("0.00"),
        property_tax_estimate_monthly=Decimal("0.00"),
        insurance_estimate_monthly=Decimal("0.00"),
        billing_authorized_at=datetime.utcnow(),
        billing_authorized_by_id=admin.id,
        billing_authorization_note="Approved from source.",
        is_active=True, created_by_id=admin.id,
    )
    db.add(terms); db.commit()
    return org, admin, tenant, prop, unit, lease, source, ti_evidence, abstract, terms


def _payload(evidence, *, amount="10000.00", key="ti-use-0001", note="Tenant improvement invoice reviewed"):
    return CommercialTIAllowanceUseIn(
        evidence_attachment_id=evidence.id,
        incurred_on=date(2026, 6, 1),
        amount=Decimal(amount),
        note=note,
        request_key=key,
    )


def test_ti_allowance_tracks_usage_remaining_and_void_without_finance():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, source, evidence, abstract, terms = _seed(db)
        before = (db.query(Charge).count(), db.query(RentInvoice).count(), db.query(GLTransaction).count())
        first = api.record_ti_use(
            prop.id, abstract.id, _payload(evidence),
            db=db, current_user=admin,
        )
        assert first.amount == Decimal("10000.00")
        assert first.allowance_total == Decimal("25000.00")
        assert first.remaining_after == Decimal("15000.00")
        assert first.status == "ACTIVE"
        second = api.record_ti_use(
            prop.id, abstract.id,
            _payload(evidence, amount="5000.00", key="ti-use-0002", note="Second tenant improvement invoice"),
            db=db, current_user=admin,
        )
        assert second.remaining_after == Decimal("10000.00")
        summary = api.ti_summary(
            prop.id, abstract.id, Response(), db=db, current_user=admin,
        )
        assert summary.allowance_total == Decimal("25000.00")
        assert summary.used_active == Decimal("15000.00")
        assert summary.remaining == Decimal("10000.00")
        assert [row.id for row in api.list_ti_uses(
            prop.id, abstract.id, Response(), db=db, current_user=admin,
        )] == [second.id, first.id]
        replay = api.record_ti_use(
            prop.id, abstract.id, _payload(evidence),
            db=db, current_user=admin,
        )
        assert replay.id == first.id
        voided = api.void_ti_use(
            prop.id, abstract.id, second.id,
            CommercialTIAllowanceVoidIn(
                voided_on=date(2026, 6, 2), reason="Duplicate invoice record",
            ),
            db=db, current_user=admin,
        )
        assert voided.status == "VOIDED"
        summary = api.ti_summary(
            prop.id, abstract.id, Response(), db=db, current_user=admin,
        )
        assert summary.used_active == Decimal("10000.00")
        assert summary.remaining == Decimal("15000.00")
        assert (db.query(Charge).count(), db.query(RentInvoice).count(),
                db.query(GLTransaction).count()) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_ti_allowance_rejects_overage_shared_evidence_and_missing_terms():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, source, evidence, abstract, terms = _seed(db)
        with pytest.raises(HTTPException) as over:
            api.record_ti_use(
                prop.id, abstract.id,
                _payload(evidence, amount="26000.00", key="ti-over-limit"),
                db=db, current_user=admin,
            )
        assert over.value.status_code == 409
        shared = EntityAttachment(
            organization_id=org.id, entity_type="leases", entity_id=lease.id,
            storage_key="ti/shared.pdf", original_name="shared.pdf",
            content_type="application/pdf", size_bytes=50,
            share_with_tenants=True, share_with_owners=False,
            uploaded_by_id=admin.id, is_active=True,
        )
        db.add(shared); db.commit()
        with pytest.raises(HTTPException) as private:
            api.record_ti_use(
                prop.id, abstract.id,
                _payload(shared, key="ti-shared-doc"),
                db=db, current_user=admin,
            )
        assert private.value.status_code == 404
        terms.ti_allowance_total = None
        db.flush()
        with pytest.raises(HTTPException) as missing:
            api.ti_summary(prop.id, abstract.id, Response(), db=db, current_user=admin)
        assert missing.value.status_code == 409
        assert db.query(CommercialTIAllowanceUse).count() == 0
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
