"""Annual Commercial CAM reconciliation uses posted estimates and central GL."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.charge import Charge
from app.models.commercial_cam_reconciliation import CommercialCAMReconciliation
from app.models.commercial_lease_abstract import CommercialLeaseAbstract, CommercialLeaseTerms
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs, commercial_lease_abstracts as abstracts
from app.routers import commercial_operating_charges as operating
from app.routers import commercial_cam_reconciliations as api
from app.schemas.commercial_operating_charge import CommercialOperatingChargeIssueIn
from app.schemas.commercial_cam_reconciliation import (
    CommercialCAMReconciliationIn, CommercialCAMReconciliationReverseIn,
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
    org = Organization(name="Commercial Recon", slug="commercial-recon")
    db.add(org); db.flush()
    admin = User(
        organization_id=org.id, role=UserRole.ADMIN, first_name="Recon", last_name="Admin",
        email="commercial-recon-admin@example.com", hashed_password="x", is_active=True,
    )
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT, first_name="Recon", last_name="Tenant",
        email="commercial-recon-tenant@example.com", hashed_password="x", is_active=True,
    )
    db.add_all((admin, tenant)); db.flush()
    prop = Property(
        organization_id=org.id, name="Commercial Recon Property",
        property_type=PropertyType.COMMERCIAL, address_line1="2 Commerce",
        city="Cleveland", state="OH", zip_code="44113", is_active=True,
    )
    db.add(prop); db.flush()
    unit = Unit(property_id=prop.id, unit_number="R-1", monthly_rent=Decimal("2500"), is_active=True)
    db.add(unit); db.flush()
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id,
        start_date=date(2026, 1, 1), end_date=date(2028, 12, 31),
        monthly_rent=Decimal("2500"), security_deposit=Decimal("0"),
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease); db.flush()
    lease_source = EntityAttachment(
        organization_id=org.id, entity_type="leases", entity_id=lease.id,
        storage_key="commercial-recon/lease.pdf", original_name="lease.pdf",
        content_type="application/pdf", size_bytes=100,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    property_evidence = EntityAttachment(
        organization_id=org.id, entity_type="properties", entity_id=prop.id,
        storage_key="commercial-recon/cam-actual.pdf", original_name="cam-actual.pdf",
        content_type="application/pdf", size_bytes=200,
        share_with_tenants=False, share_with_owners=False,
        uploaded_by_id=admin.id, is_active=True,
    )
    db.add_all((lease_source, property_evidence)); db.flush()
    abstract = CommercialLeaseAbstract(
        organization_id=org.id, property_id=prop.id, lease_id=lease.id,
        source_attachment_id=lease_source.id, rent_commencement_on=date(2026, 1, 1),
        created_by_id=admin.id, updated_by_id=admin.id, is_active=True,
    )
    db.add(abstract); db.flush()
    terms = CommercialLeaseTerms(
        organization_id=org.id, property_id=prop.id, lease_id=lease.id,
        abstract_id=abstract.id, source_attachment_id=lease_source.id,
        revision=1, effective_on=date(2026, 1, 1),
        base_rent_monthly=Decimal("2500.00"),
        cam_estimate_monthly=Decimal("100.00"),
        property_tax_estimate_monthly=Decimal("50.00"),
        insurance_estimate_monthly=Decimal("25.00"),
        cam_share_percent=Decimal("10.0000"),
        billing_authorized_at=datetime.utcnow(), billing_authorized_by_id=admin.id,
        billing_authorization_note="Internal source review completed.",
        is_active=True, created_by_id=admin.id,
    )
    ar = GLAccount(
        organization_id=org.id, gl_number="1201", name="Commercial receivable",
        account_type="ASSET", is_active=True,
    )
    income = GLAccount(
        organization_id=org.id, gl_number="4301", name="CAM recovery income",
        account_type="INCOME", is_active=True,
    )
    db.add_all((terms, ar, income)); db.commit()
    return org, admin, tenant, prop, unit, lease, lease_source, property_evidence, abstract, terms, ar, income


def _estimated(db, admin, prop, abstract, ar, income):
    return operating.issue_operating_charge(
        prop.id, abstract.id,
        CommercialOperatingChargeIssueIn(
            kind="CAM", period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
            posting_on=date(2026, 3, 1), due_on=date(2026, 3, 10),
            receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
            request_key="recon-estimate-2026-03",
        ),
        db=db, current_user=admin,
    )


def _payload(evidence, ar, income, actual, key):
    return CommercialCAMReconciliationIn(
        reconciliation_year=2026,
        evidence_attachment_id=evidence.id,
        actual_cam_total=Decimal(actual),
        posting_on=date(2026, 9, 30), due_on=date(2026, 10, 15),
        receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
        request_key=key,
    )


def test_positive_cam_true_up_posts_charge_and_reverses():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, lease_source, evidence, abstract, terms, ar, income = _seed(db)
        estimated = _estimated(db, admin, prop, abstract, ar, income)
        assert estimated.cam_amount == Decimal("100.00")
        before_charge_count = db.query(Charge).count()
        row = api.record_reconciliation(
            prop.id, abstract.id,
            _payload(evidence, ar, income, "2000.00", "cam-recon-positive-2026"),
            db=db, current_user=admin,
        )
        assert row.actual_tenant_share == Decimal("200.00")
        assert row.estimated_cam_billed == Decimal("100.00")
        assert row.true_up_amount == Decimal("100.00")
        assert row.status == "POSTED"
        assert row.charge_id is not None and row.gl_transaction_id is not None
        assert db.query(Charge).count() == before_charge_count + 1
        entries = db.query(GLEntry).filter(GLEntry.transaction_id == row.gl_transaction_id).all()
        assert len(entries) == 2
        replay = api.record_reconciliation(
            prop.id, abstract.id,
            _payload(evidence, ar, income, "2000.00", "cam-recon-positive-2026"),
            db=db, current_user=admin,
        )
        assert replay.id == row.id
        reversed_row = api.reverse_reconciliation(
            prop.id, abstract.id, row.id,
            CommercialCAMReconciliationReverseIn(
                reversal_on=date(2026, 9, 30), reason="Corrected annual source",
            ),
            db=db, current_user=admin,
        )
        assert reversed_row.status == "REVERSED"
        assert reversed_row.reversal_transaction_id is not None
        assert db.get(GLTransaction, row.gl_transaction_id).is_reversed is True
        assert db.get(Charge, row.charge_id).is_active is False
    finally:
        db.rollback(); db.close(); engine.dispose()


@pytest.mark.parametrize(
    ("actual", "expected_true_up", "expected_status", "charge_delta", "gl_delta"),
    [
        ("500.00", Decimal("-50.00"), "POSTED", 0, 1),
        ("1000.00", Decimal("0.00"), "ZERO", 0, 0),
    ],
)
def test_negative_credit_and_zero_cam_true_up(actual, expected_true_up, expected_status, charge_delta, gl_delta):
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, lease_source, evidence, abstract, terms, ar, income = _seed(db)
        _estimated(db, admin, prop, abstract, ar, income)
        charges_before = db.query(Charge).count()
        gl_before = db.query(GLTransaction).count()
        row = api.record_reconciliation(
            prop.id, abstract.id,
            _payload(evidence, ar, income, actual, "cam-recon-" + expected_status.lower()),
            db=db, current_user=admin,
        )
        assert row.true_up_amount == expected_true_up
        assert row.status == expected_status
        assert db.query(Charge).count() == charges_before + charge_delta
        assert db.query(GLTransaction).count() == gl_before + gl_delta
        if expected_true_up < 0:
            assert row.charge_id is None and row.gl_transaction_id is not None
            entries = db.query(GLEntry).filter(GLEntry.transaction_id == row.gl_transaction_id).all()
            income_entry = next(e for e in entries if e.gl_account_id == income.id)
            receivable_entry = next(e for e in entries if e.gl_account_id == ar.id)
            assert income_entry.debit == Decimal("50.00")
            assert receivable_entry.credit == Decimal("50.00")
        else:
            assert row.charge_id is None and row.gl_transaction_id is None
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_cam_reconciliation_requires_private_scoped_evidence_and_share():
    db, engine = _db()
    try:
        org, admin, tenant, prop, unit, lease, lease_source, evidence, abstract, terms, ar, income = _seed(db)
        _estimated(db, admin, prop, abstract, ar, income)
        evidence.share_with_tenants = True
        db.flush()
        with pytest.raises(HTTPException) as shared:
            api.record_reconciliation(
                prop.id, abstract.id,
                _payload(evidence, ar, income, "2000.00", "cam-recon-shared"),
                db=db, current_user=admin,
            )
        assert shared.value.status_code == 404
        evidence.share_with_tenants = False
        terms.cam_share_percent = None
        db.flush()
        with pytest.raises(HTTPException) as no_share:
            api.record_reconciliation(
                prop.id, abstract.id,
                _payload(evidence, ar, income, "2000.00", "cam-recon-no-share"),
                db=db, current_user=admin,
            )
        assert no_share.value.status_code == 409
        assert db.query(CommercialCAMReconciliation).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
