"""HOA registry records do not establish association authority or post accounting."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.contact import Contact
from app.models.hoa_association import HOAContactLink
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.hoa_association import HOAAssociation, HOAPropertyMembership
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as api
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=api.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=api.HOA_FEATURE_KEY, allowed=True)
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="HOA A", slug="hoa-a")
    b = Organization(name="HOA B", slug="hoa-b")
    db.add_all([a, b])
    db.flush()
    people = []
    for org, role, label in (
        (a, UserRole.ADMIN, "admin"), (a, UserRole.OWNER, "owner"),
        (a, UserRole.MANAGER, "manager"), (a, UserRole.TENANT, "tenant"),
        (b, UserRole.ADMIN, "foreign"),
    ):
        row = User(organization_id=org.id, role=role, first_name="HOA",
                   last_name=label, email=f"hoa-{label}@example.com",
                   hashed_password="x", is_active=True)
        db.add(row)
        people.append(row)
    db.flush()
    props = []
    for org, label in ((a, "Assigned"), (a, "Unassigned"), (b, "Foreign")):
        prop = Property(organization_id=org.id, name=label,
                        address_line1="100 Main", city="Cleveland",
                        state="OH", zip_code="44113", is_active=True)
        db.add(prop)
        props.append(prop)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id, user_id=people[2].id,
                              role=UserRole.MANAGER, is_active=True))
    db.commit()
    return people, props


def _in(name="Recorded HOA", property_ids=None):
    return HOAAssociationIn(name=name, property_ids=property_ids or [])


def test_assoc_membership_multiple_properties_and_restricted_manager_view():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        created = api.create_association(_in(property_ids=[assigned.id, unassigned.id]),
                                         db=db, current_user=admin)
        assert set(created.property_ids) == {assigned.id, unassigned.id}
        assert api.list_associations(Response(), db=db, current_user=manager)[0].property_ids == [assigned.id]
        with pytest.raises(HTTPException) as exc:
            api.create_association(_in("Unauthorized", [assigned.id]),
                                   db=db, current_user=manager)
        assert exc.value.status_code == 403
        assert len(api.list_associations(Response(), db=db, current_user=owner)) == 1
        for actor in (tenant, foreign):
            with pytest.raises(HTTPException):
                api.get_association(created.id, Response(), db=db, current_user=actor)
        updated = api.update_association(created.id, _in("Renamed HOA", [unassigned.id]),
                                         db=db, current_user=owner)
        assert updated.property_ids == [unassigned.id]
        with pytest.raises(HTTPException) as exc:
            api.get_association(created.id, Response(), db=db, current_user=manager)
        assert exc.value.status_code == 404
        assert api.list_associations(Response(), db=db, current_user=manager) == []
        assert db.query(HOAPropertyMembership).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_association").count() == 2
        assert db.query(Charge).count() == db.query(Lease).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_duplicate_name_cross_org_property_probing_and_archival():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        one = api.create_association(_in("  Lake  HOA ", [assigned.id]),
                                     db=db, current_user=admin)
        assert one.name == "Lake HOA"
        for value in ("lake hoa", "Lake HOA"):
            with pytest.raises(HTTPException) as exc:
                api.create_association(_in(value, [assigned.id]), db=db, current_user=admin)
            assert exc.value.status_code == 409
        with pytest.raises(HTTPException) as exc:
            api.create_association(_in("Probe", [other.id]), db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.get_association(one.id, Response(), db=db, current_user=foreign)
        assert exc.value.status_code == 404
        api.archive_association(one.id, db=db, current_user=admin)
        assert api.list_associations(Response(), db=db, current_user=admin) == []
        assert db.query(HOAAssociation).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_association").count() == 2
        with pytest.raises(ValueError):
            _in(" ")
        with pytest.raises(ValueError):
            _in(property_ids=[assigned.id, assigned.id])
        with pytest.raises(ValueError):
            _in(property_ids=[-1])
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_associations")
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_property_memberships")
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_rechecks_feature_permission_assignment_and_active_property(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        one = api.create_association(_in(property_ids=[assigned.id]),
                                     db=db, current_user=admin)
        response = Response()
        api.get_association(one.id, response, db=db, current_user=manager)
        assert response.headers["cache-control"] == "no-store"
        assignment = db.query(PropertyAssignment).filter(
            PropertyAssignment.property_id == assigned.id,
            PropertyAssignment.user_id == manager.id,
        ).one()
        assignment.is_active = False
        db.flush()
        assert api.list_associations(Response(), db=db, current_user=manager) == []
        assigned.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.create_association(_in("Closed", [assigned.id]), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            api.list_associations(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=api.FEATURE_KEY, allowed=False)
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_associations(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()



def test_same_property_multiple_associations_and_deactivated_admin_guard():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        first = api.create_association(_in("North HOA", [assigned.id]), db=db, current_user=admin)
        second = api.create_association(_in("South HOA", [assigned.id]), db=db, current_user=owner)
        assert first.id != second.id
        assert len(api.list_associations(Response(), db=db, current_user=manager)) == 2
        assert db.query(HOAPropertyMembership).filter(
            HOAPropertyMembership.property_id == assigned.id,
        ).count() == 2
        admin.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_associations(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()



def test_contact_links_scope_revocation_archival_and_property_unlink(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        local = Contact(organization_id=admin.organization_id, display_name="Staff Contact",
                        contact_type="PERSON", is_active=True)
        far = Contact(organization_id=foreign.organization_id, display_name="Foreign Contact",
                      contact_type="PERSON", is_active=True)
        db.add_all([local, far]); db.commit()
        assoc = api.create_association(_in("Contact HOA", [assigned.id, unassigned.id]),
                                       db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.add_contact_link(assoc.id, HOAContactLinkIn(property_id=assigned.id,
                                 contact_id=far.id), db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.add_contact_link(assoc.id, HOAContactLinkIn(property_id=other.id,
                                 contact_id=local.id), db=db, current_user=admin)
        assert exc.value.status_code == 404
        saved = api.add_contact_link(assoc.id, HOAContactLinkIn(
            property_id=assigned.id, contact_id=local.id), db=db, current_user=admin)
        assert saved.contact_name == "Staff Contact"
        response = Response()
        listed = api.list_contact_links(assoc.id, assigned.id, response,
                                        db=db, current_user=manager)
        assert [r.id for r in listed] == [saved.id]
        assert response.headers["cache-control"] == "no-store"
        with pytest.raises(HTTPException) as exc:
            api.list_contact_links(assoc.id, unassigned.id, Response(),
                                   db=db, current_user=manager)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.add_contact_link(assoc.id, HOAContactLinkIn(
                property_id=assigned.id, contact_id=local.id), db=db, current_user=manager)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.add_contact_link(assoc.id, HOAContactLinkIn(
                property_id=assigned.id, contact_id=local.id), db=db, current_user=admin)
        assert exc.value.status_code == 409
        monkeypatch.setattr(api, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PEOPLE.CONTACTS")
        with pytest.raises(HTTPException) as exc:
            api.list_contact_links(assoc.id, assigned.id, Response(),
                                   db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        api.update_association(assoc.id, _in("Contact HOA", [unassigned.id]),
                               db=db, current_user=admin)
        assert db.query(HOAContactLink).one().is_active is False
        api.update_association(assoc.id, _in("Contact HOA", [assigned.id, unassigned.id]),
                               db=db, current_user=admin)
        assert api.list_contact_links(assoc.id, assigned.id, Response(),
                                      db=db, current_user=admin) == []
        restored = api.add_contact_link(assoc.id, HOAContactLinkIn(
            property_id=assigned.id, contact_id=local.id), db=db, current_user=admin)
        assert restored.id == saved.id
        api.remove_contact_link(assoc.id, saved.id, assigned.id, db=db, current_user=owner)
        assert api.list_contact_links(assoc.id, assigned.id, Response(),
                                      db=db, current_user=admin) == []
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_contact_links")
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_contact_links_hidden_for_deactivated_contact_and_foreign_organization():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        contact = Contact(organization_id=admin.organization_id, display_name="Inactive HOA contact",
                          contact_type="PERSON", is_active=True)
        db.add(contact); db.commit()
        assoc = api.create_association(_in("Second HOA", [assigned.id]),
                                       db=db, current_user=admin)
        added = api.add_contact_link(assoc.id, HOAContactLinkIn(
            property_id=assigned.id, contact_id=contact.id), db=db, current_user=admin)
        contact.is_active = False
        db.flush()
        assert api.list_contact_links(assoc.id, assigned.id, Response(),
                                      db=db, current_user=admin) == []
        with pytest.raises(HTTPException) as exc:
            api.list_contact_links(assoc.id, assigned.id, Response(),
                                   db=db, current_user=foreign)
        assert exc.value.status_code == 404
        db.rollback()
        assert db.query(HOAContactLink).filter(HOAContactLink.id == added.id).count() == 1
    finally:
        db.close(); engine.dispose()
