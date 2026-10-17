"""Full Vendor company records are tenant scoped and distinct from VENDOR users."""
from __future__ import annotations

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest
import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bill import Bill
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.routers import vendors
from app.schemas.vendor import VendorCreate, VendorUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Vendor Company One", slug="vendor-company-one")
    other = Organization(name="Vendor Company Two", slug="vendor-company-two")
    db.add_all([org, other])
    db.flush()
    people = []
    for o, role, name in (
        (org, UserRole.ADMIN, "Admin"), (org, UserRole.OWNER, "Owner"),
        (org, UserRole.MANAGER, "Manager"), (org, UserRole.VENDOR, "VendorContact"),
        (other, UserRole.VENDOR, "ForeignVendor"), (other, UserRole.ADMIN, "ForeignAdmin"),
    ):
        row = User(organization_id=o.id, first_name=name, last_name="Company",
                   email=f"{name.lower()}@vendor-company.example", hashed_password="x",
                   role=role, is_active=True)
        db.add(row)
        people.append(row)
    db.commit()
    return people


def _payload(**kwargs):
    return VendorCreate(company_name=" Acme Plumbing ", trade="Plumbing", 
                        business_email="dispatch@example.com", phone="555-0176", **kwargs)


def test_company_lifecycle_search_audit_and_no_bill_mutation(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, contact, foreign_contact, foreign_admin = _seed(db)
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: True)
        bills_before = db.query(Bill).count()
        created = vendors.create_vendor(_payload(contact_user_id=contact.id), db=db, current_user=admin)
        assert created.id and created.organization_id == admin.organization_id
        assert created.company_name == "Acme Plumbing"
        assert created.contact_user_id == contact.id
        listed = vendors.list_vendors(Response(), search="Acme", db=db, current_user=owner)
        assert listed.total == 1 and listed.items[0].id == created.id
        changed = vendors.update_vendor(
            created.id, VendorUpdate(trade="Heating", contact_user_id=None),
            db=db, current_user=admin,
        )
        assert changed.trade == "Heating" and changed.contact_user_id is None
        assert vendors.get_vendor(created.id, Response(), db=db, current_user=owner).company_name == "Acme Plumbing"
        vendors.delete_vendor(created.id, db=db, current_user=admin)
        assert vendors.list_vendors(Response(), db=db, current_user=admin).total == 0
        assert vendors.list_vendors(Response(), include_inactive=True, db=db, current_user=owner).total == 1
        with pytest.raises(HTTPException) as exc:
            vendors.update_vendor(created.id, VendorUpdate(company_name="Still Deleted"), db=db, current_user=admin)
        assert exc.value.status_code == 409
        restored = vendors.restore_vendor(created.id, db=db, current_user=admin)
        assert restored.is_active and restored.deleted_at is None
        assert vendors.list_vendors(Response(), db=db, current_user=admin).total == 1
        assert db.query(Bill).count() == bills_before
        actions = [a.action for a in db.query(AuditLog).filter(AuditLog.entity_type == "vendor").all()]
        assert actions == ["created", "updated", "deactivated", "restored"]
    finally:
        db.close()
        engine.dispose()


def test_org_role_contact_and_permission_checks(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, contact, foreign_contact, foreign_admin = _seed(db)
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: True)
        with pytest.raises(HTTPException) as exc:
            vendors.create_vendor(_payload(contact_user_id=foreign_contact.id), db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            vendors.create_vendor(_payload(contact_user_id=manager.id), db=db, current_user=admin)
        assert exc.value.status_code == 404
        own = vendors.create_vendor(_payload(), db=db, current_user=admin)
        foreign = vendors.create_vendor(_payload(), db=db, current_user=foreign_admin)
        for actor in (owner, manager, contact, foreign_contact):
            with pytest.raises(HTTPException) as exc:
                vendors.create_vendor(_payload(), db=db, current_user=actor)
            assert exc.value.status_code == 403
        for actor in (manager, contact, foreign_contact):
            with pytest.raises(HTTPException) as exc:
                vendors.list_vendors(Response(), db=db, current_user=actor)
            assert exc.value.status_code == 403
        for action in (
            lambda: vendors.get_vendor(foreign.id, Response(), db=db, current_user=admin),
            lambda: vendors.update_vendor(foreign.id, VendorUpdate(company_name="Probe"), db=db, current_user=admin),
            lambda: vendors.delete_vendor(foreign.id, db=db, current_user=admin),
            lambda: vendors.restore_vendor(foreign.id, db=db, current_user=admin),
        ):
            with pytest.raises(HTTPException) as exc:
                action()
            assert exc.value.status_code == 404
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            vendors.list_vendors(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(Vendor).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_validation_archived_actors_and_no_tax_fields(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, contact, foreign_contact, foreign_admin = _seed(db)
        monkeypatch.setattr(vendors, "permission_allows_user", lambda *a, **kw: True)
        with pytest.raises(ValueError):
            VendorCreate(company_name="   ")
        with pytest.raises(ValueError):
            VendorCreate(company_name="Plumbers", business_email="invalid")
        with pytest.raises(ValueError):
            VendorCreate(company_name="Plumbers", contact_user_id=0)
        created = vendors.create_vendor(_payload(), db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            vendors.update_vendor(created.id, VendorUpdate(company_name=None), db=db, current_user=admin)
        assert exc.value.status_code == 422
        contact.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            vendors.update_vendor(created.id, VendorUpdate(contact_user_id=contact.id), db=db, current_user=admin)
        assert exc.value.status_code == 404
        admin.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            vendors.get_vendor(created.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert not hasattr(created, "tin")
        assert not hasattr(created, "tax_id")
        assert db.query(Vendor).count() == 1
    finally:
        db.close()
        engine.dispose()
