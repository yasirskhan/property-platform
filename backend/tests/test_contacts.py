"""Phase 4 address book is isolated, auditable and independent of account identities."""
from __future__ import annotations

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest
import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.contact import Contact
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.routers import contacts as api
from app.schemas.contact import ContactCreate, ContactUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Contacts One", slug="contacts-one")
    other = Organization(name="Contacts Other", slug="contacts-other")
    db.add_all([org, other])
    db.flush()
    users = []
    for company, role, name in (
        (org, UserRole.ADMIN, "Admin"), (org, UserRole.OWNER, "Owner"),
        (org, UserRole.MANAGER, "Manager"), (org, UserRole.TENANT, "Tenant"),
        (other, UserRole.ADMIN, "Other"),
    ):
        user = User(
            organization_id=company.id, role=role, first_name=name, last_name="Contact",
            email=f"{name.lower()}@contacts-test.example", hashed_password="x", is_active=True,
        )
        db.add(user)
        users.append(user)
    db.commit()
    return users


def _create(name="External Designer"):
    return ContactCreate(
        display_name=name, contact_type="PERSON", company_name="Outside Studio",
        email="designer@example.com", phone="555-0146", city="Cleveland",
    )


def test_contact_crud_search_deactivate_restore_does_not_touch_vendors(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, tenant, other_admin = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        users_before, vendors_before = db.query(User).count(), db.query(Vendor).count()
        made = api.create_contact(_create(), db=db, current_user=admin)
        assert made.id and made.organization_id == admin.organization_id
        assert made.display_name == "External Designer"
        listed = api.list_contacts(Response(), search="studio", db=db, current_user=manager)
        assert listed.total == 1 and listed.items[0].id == made.id
        assert api.get_contact(made.id, Response(), db=db, current_user=owner).id == made.id
        changed = api.update_contact(made.id, ContactUpdate(phone="555-9999"), db=db, current_user=admin)
        assert changed.phone == "555-9999"
        api.deactivate_contact(made.id, db=db, current_user=admin)
        assert api.list_contacts(Response(), db=db, current_user=owner).total == 0
        assert api.list_contacts(Response(), include_inactive=True, db=db, current_user=owner).total == 1
        with pytest.raises(HTTPException) as exc:
            api.update_contact(made.id, ContactUpdate(phone="no"), db=db, current_user=admin)
        assert exc.value.status_code == 409
        restored = api.restore_contact(made.id, db=db, current_user=admin)
        assert restored.is_active and restored.deleted_at is None
        actions = [a.action for a in db.query(AuditLog).filter_by(entity_type="contact").order_by(AuditLog.id).all()]
        assert actions == ["created", "updated", "deactivated", "restored"]
        assert db.query(User).count() == users_before
        assert db.query(Vendor).count() == vendors_before
        assert not hasattr(restored, "tax_id")
    finally:
        db.close()
        engine.dispose()


def test_cross_org_role_visibility_and_user_menu_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, tenant, other_admin = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        own = api.create_contact(_create(), db=db, current_user=admin)
        foreign = api.create_contact(_create("Foreign Private"), db=db, current_user=other_admin)
        assert api.list_contacts(Response(), db=db, current_user=owner).total == 1
        assert api.list_contacts(Response(), db=db, current_user=other_admin).items[0].id == foreign.id
        for call in (
            lambda: api.get_contact(foreign.id, Response(), db=db, current_user=admin),
            lambda: api.update_contact(foreign.id, ContactUpdate(phone="x"), db=db, current_user=admin),
            lambda: api.deactivate_contact(foreign.id, db=db, current_user=admin),
            lambda: api.restore_contact(foreign.id, db=db, current_user=admin),
        ):
            with pytest.raises(HTTPException) as exc:
                call()
            assert exc.value.status_code == 404
        for actor in (owner, manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_contact(_create(), db=db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.list_contacts(Response(), db=db, current_user=tenant)
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: False)
        for call in (
            lambda: api.list_contacts(Response(), db=db, current_user=admin),
            lambda: api.update_contact(own.id, ContactUpdate(phone="denied"), db=db, current_user=admin),
        ):
            with pytest.raises(HTTPException) as exc:
                call()
            assert exc.value.status_code == 403
        admin.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.list_contacts(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(Contact).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_input_constraints_and_no_pii_in_audit(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        with pytest.raises(ValueError):
            _create("  ")
        with pytest.raises(ValueError):
            ContactCreate(display_name="x", email="wrong-format")
        row = api.create_contact(_create(), db=db, current_user=admin)
        with pytest.raises(ValueError):
            ContactUpdate(display_name=" ")
        for payload in (ContactUpdate(), ContactUpdate(display_name=None), ContactUpdate(contact_type=None)):
            with pytest.raises(HTTPException) as exc:
                api.update_contact(row.id, payload, db=db, current_user=admin)
            assert exc.value.status_code == 422
        with pytest.raises(HTTPException) as exc:
            api.list_contacts(Response(), search="x"*101, db=db, current_user=admin)
        assert exc.value.status_code == 422
        audit = db.query(AuditLog).filter_by(entity_type="contact").all()
        assert len(audit) == 1
        for item in audit:
            assert "designer@example.com" not in (item.new_value or "")
            assert "555-0146" not in (item.new_value or "")
        assert db.query(Contact).count() == 1
    finally:
        db.close()
        engine.dispose()
