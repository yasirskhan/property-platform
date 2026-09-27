"""Vendor policy expiry metadata never changes property expenses or GL."""
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
from app.models.audit_log import AuditLog
from app.models.expense import PropertyExpense
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_insurance import VendorInsurance
from app.routers import vendors, vendor_insurance as insurance
from app.schemas.vendor import VendorCreate
from app.schemas.vendor_insurance import VendorInsuranceCreate, VendorInsuranceUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Vendor Insurance One", slug="vendor-insurance-one")
    second = Organization(name="Vendor Insurance Two", slug="vendor-insurance-two")
    db.add_all([first, second])
    db.flush()
    users = []
    for org, role, label in (
        (first, UserRole.ADMIN, "Admin"),
        (first, UserRole.OWNER, "Owner"),
        (first, UserRole.MANAGER, "Manager"),
        (second, UserRole.ADMIN, "OtherAdmin"),
    ):
        row = User(organization_id=org.id, role=role, first_name=label,
                   last_name="Insurance", email=f"{label.lower()}@vendor-insurance.example",
                   hashed_password="x", is_active=True)
        db.add(row)
        users.append(row)
    db.commit()
    return users


def _policy(**kw):
    return VendorInsuranceCreate(
        carrier=" Insurer Ltd ", coverage_type="General liability",
        policy_number="GL-100", coverage_amount=Decimal("1000000.00"),
        effective_date=date(2026, 1, 1), expiration_date=date(2026, 10, 1),
        **kw,
    )


def test_policy_lifecycle_expiry_status_audit_and_no_gl_postings(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, other = _seed(db)
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: True)
        company = vendors.create_vendor(VendorCreate(company_name="Acme Insurance Test"),
                                        db=db, current_user=admin)
        before_gl = db.query(GLTransaction).count()
        before_expense = db.query(PropertyExpense).count()
        created = insurance.create_vendor_insurance(
            company.id, _policy(), db=db, current_user=admin)
        assert created.carrier == "Insurer Ltd" and created.vendor_id == company.id
        asof = date(2026, 9, 1)
        listed = insurance.list_vendor_insurance(
            company.id, Response(), as_of=asof, db=db, current_user=owner)
        assert listed.total == 1
        assert listed.items[0].status == "EXPIRING_30_DAYS"
        assert insurance.list_vendor_insurance(
            company.id, Response(), as_of=date(2026, 10, 2),
            db=db, current_user=admin).items[0].status == "EXPIRED"
        updated = insurance.update_vendor_insurance(
            company.id, created.id,
            VendorInsuranceUpdate(expiration_date=date(2027, 10, 1)),
            db=db, current_user=admin,
        )
        assert updated.expiration_date == date(2027, 10, 1)
        assert insurance.list_vendor_insurance(
            company.id, Response(), as_of=asof, db=db,
            current_user=owner).items[0].status == "CURRENT"
        insurance.delete_vendor_insurance(company.id, created.id, db=db, current_user=admin)
        assert insurance.list_vendor_insurance(
            company.id, Response(), db=db, current_user=owner).total == 0
        inactive = insurance.list_vendor_insurance(
            company.id, Response(), include_inactive=True, as_of=asof,
            db=db, current_user=owner)
        assert inactive.total == 1 and inactive.items[0].status == "INACTIVE"
        restored = insurance.restore_vendor_insurance(
            company.id, created.id, db=db, current_user=admin)
        assert restored.is_active
        assert db.query(GLTransaction).count() == before_gl
        assert db.query(PropertyExpense).count() == before_expense
        actions = [a.action for a in db.query(AuditLog).filter(
            AuditLog.entity_type == "vendor_insurance",
        ).order_by(AuditLog.id).all()]
        assert actions == ["created", "updated", "deactivated", "restored"]
    finally:
        db.close()
        engine.dispose()


def test_cross_org_roles_invalid_date_and_vendor_archive_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, other = _seed(db)
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: True)
        company = vendors.create_vendor(VendorCreate(company_name="Local"), db=db, current_user=admin)
        foreign = vendors.create_vendor(VendorCreate(company_name="Foreign"), db=db, current_user=other)
        policy = insurance.create_vendor_insurance(
            company.id, _policy(), db=db, current_user=admin)
        with pytest.raises(ValueError):
            VendorInsuranceCreate(carrier=" ", coverage_type="Liability",
                                  expiration_date=date(2026, 1, 1))
        with pytest.raises(ValueError):
            VendorInsuranceCreate(carrier="Carrier", coverage_type="Liability",
                                  effective_date=date(2027, 1, 1),
                                  expiration_date=date(2026, 1, 1))
        for actor in (owner, manager):
            with pytest.raises(HTTPException) as exc:
                insurance.create_vendor_insurance(company.id, _policy(),
                                                  db=db, current_user=actor)
            assert exc.value.status_code == 403
        for actor in (manager, other):
            with pytest.raises(HTTPException) as exc:
                insurance.list_vendor_insurance(company.id, Response(),
                                               db=db, current_user=actor)
            assert exc.value.status_code in (403, 404)
        for action in (
            lambda: insurance.list_vendor_insurance(foreign.id, Response(), db=db, current_user=admin),
            lambda: insurance.update_vendor_insurance(foreign.id, policy.id,
                     VendorInsuranceUpdate(carrier="Wrong"), db=db, current_user=admin),
            lambda: insurance.delete_vendor_insurance(foreign.id, policy.id, db=db, current_user=admin),
            lambda: insurance.restore_vendor_insurance(foreign.id, policy.id, db=db, current_user=admin),
            lambda: insurance.update_vendor_insurance(company.id, 99999,
                     VendorInsuranceUpdate(carrier="Wrong"), db=db, current_user=admin),
        ):
            with pytest.raises(HTTPException) as exc:
                action()
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            insurance.update_vendor_insurance(
                company.id, policy.id,
                VendorInsuranceUpdate(expiration_date=date(2025, 1, 1)),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 422
        vendors.delete_vendor(company.id, db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            insurance.create_vendor_insurance(company.id, _policy(),
                                              db=db, current_user=admin)
        assert exc.value.status_code == 409
    finally:
        db.close()
        engine.dispose()


def test_expiry_today_upcoming_revocation_and_scoped_attachments(monkeypatch):
    from app.services.entity_notes import resolve_note_target

    db, engine = _session()
    try:
        admin, owner, manager, other = _seed(db)
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: True)
        company = vendors.create_vendor(VendorCreate(company_name="Local"),
                                        db=db, current_user=admin)
        upcoming = insurance.create_vendor_insurance(company.id, _policy(
            effective_date=date(2026, 10, 1), expiration_date=date(2027, 10, 1)
        ), db=db, current_user=admin)
        asof = date(2026, 9, 1)
        assert insurance.list_vendor_insurance(company.id, Response(),
            as_of=asof, db=db, current_user=admin).items[0].status == "UPCOMING"
        insurance.update_vendor_insurance(
            company.id, upcoming.id, VendorInsuranceUpdate(
                effective_date=date(2026, 1, 1), expiration_date=date(2026, 9, 1)),
            db=db, current_user=admin)
        assert insurance.list_vendor_insurance(company.id, Response(),
            as_of=asof, db=db, current_user=admin).items[0].status == "EXPIRING_30_DAYS"
        clean, row, scope = resolve_note_target(
            db, current_user=owner, entity_type="vendor_insurances",
            entity_id=upcoming.id,
        )
        assert clean == "vendor_insurances" and scope == admin.organization_id
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            insurance.list_vendor_insurance(company.id, Response(),
                                            db=db, current_user=owner)
        assert exc.value.status_code == 403
        # Entity notes uses its own resolver; revoke that permission too.
        from app.services import entity_notes
        monkeypatch.setattr(entity_notes, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            resolve_note_target(db, current_user=owner,
                                entity_type="vendor_insurances",
                                entity_id=upcoming.id)
        assert exc.value.status_code == 403
        assert db.query(VendorInsurance).count() == 1
    finally:
        db.close()
        engine.dispose()
