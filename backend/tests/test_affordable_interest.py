"""Staff interest links never become ordered HUD/LIHTC waiting-list decisions."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.affordable_interest import AffordableInterest
from app.models.affordable_program import AffordableProgram
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.contact import Contact
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.prospect import Prospect
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_interest as api
from app.routers import affordable_programs as programs
from app.routers import prospects as crm
from app.schemas.affordable_interest import AffordableInterestIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Interest Org", slug="interest-org")
    other = Organization(name="Other Interest Org", slug="other-interest-org")
    db.add_all([org, other])
    db.flush()
    users = []
    for o, role, name in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        u = User(organization_id=o.id, role=role, first_name=name, last_name="Interest",
                 email=f"program-interest-{name}@example.com", hashed_password="x", is_active=True)
        db.add(u)
        users.append(u)
    db.flush()
    props = []
    for o, name in ((org, "Assigned"), (org, "Different"), (other, "Foreign")):
        p = Property(organization_id=o.id, name=name, address_line1="100 Recorded Street",
                     city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(p)
        props.append(p)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    programs_rows = []
    for p in props:
        row = AffordableProgram(
            organization_id=p.organization_id, property_id=p.id,
            program_type="LIHTC", label="Recorded label",
            is_active=True,
        )
        db.add(row)
        programs_rows.append(row)
    db.flush()
    prospects = []
    for p, name in zip(props, ("Recorded Contact", "Different Contact", "Foreign Contact")):
        contact = Contact(organization_id=p.organization_id, display_name=name, is_active=True)
        db.add(contact)
        db.flush()
        lead = Prospect(organization_id=p.organization_id, property_id=p.id,
                        contact_id=contact.id, stage="NEW", source="OTHER", is_active=True)
        db.add(lead)
        prospects.append(lead)
    db.commit()
    return users, props, programs_rows, prospects


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=programs.FEATURE_KEY, allowed=True),
    ])
    monkeypatch.setattr(crm, "permission_allows_user", lambda *a, **k: True)


def test_interest_lifecycle_and_current_crm_property_scope():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, foreign_prop), programs_rows, leads = _seed(db)
        item = api.record_interest(prop.id, programs_rows[0].id,
                                   AffordableInterestIn(prospect_id=leads[0].id),
                                   db=db, current_user=admin)
        assert item.contact_name == "Recorded Contact"
        assert item.program_id == programs_rows[0].id
        assert not hasattr(item, "priority") and not hasattr(item, "eligibility")
        response = Response()
        listed = api.list_interest(prop.id, programs_rows[0].id, response,
                                   db=db, current_user=manager)
        assert response.headers["cache-control"] == "no-store"
        assert [x.prospect_id for x in listed] == [leads[0].id]
        for wrong in (leads[1], leads[2]):
            with pytest.raises(HTTPException) as exc:
                api.record_interest(prop.id, programs_rows[0].id,
                                    AffordableInterestIn(prospect_id=wrong.id),
                                    db=db, current_user=admin)
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.record_interest(prop.id, programs_rows[0].id,
                                AffordableInterestIn(prospect_id=leads[0].id),
                                db=db, current_user=admin)
        assert exc.value.status_code == 409
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.record_interest(prop.id, programs_rows[0].id,
                                    AffordableInterestIn(prospect_id=leads[0].id),
                                    db=db, current_user=actor)
            assert exc.value.status_code == 403
        for actor, property_id in ((manager, other.id), (manager, foreign_prop.id),
                                   (foreign, prop.id)):
            with pytest.raises(HTTPException) as exc:
                api.list_interest(property_id, programs_rows[0].id, Response(),
                                  db=db, current_user=actor)
            assert exc.value.status_code == 404
        api.archive_interest(prop.id, programs_rows[0].id, item.id, db=db, current_user=owner)
        assert api.list_interest(prop.id, programs_rows[0].id, Response(), db=db, current_user=admin) == []
        assert db.query(AffordableInterest).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "affordable_program_interest").count() == 2
        assert db.query(Lease).count() == 0 and db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_revoked_crm_or_compliance_permission_denies_prospect_names(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, foreign_prop), programs_rows, leads = _seed(db)
        api.record_interest(prop.id, programs_rows[0].id,
                            AffordableInterestIn(prospect_id=leads[0].id),
                            db=db, current_user=admin)
        monkeypatch.setattr(crm, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.list_interest(prop.id, programs_rows[0].id, Response(),
                              db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(crm, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=programs.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_interest(prop.id, programs_rows[0].id, Response(),
                              db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=programs.FEATURE_KEY, allowed=True),
        ])
        contact = db.query(Contact).filter(Contact.id == leads[0].contact_id).one()
        contact.is_active = False
        db.flush()
        assert api.list_interest(prop.id, programs_rows[0].id, Response(),
                                 db=db, current_user=admin) == []
        assert db.query(AffordableInterest).count() == 1
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_manager_assignment_and_archived_program_isolation():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, foreign_prop), programs_rows, leads = _seed(db)
        api.record_interest(prop.id, programs_rows[0].id,
                            AffordableInterestIn(prospect_id=leads[0].id),
                            db=db, current_user=admin)
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=prop.id, user_id=manager.id).one()
        assignment.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_interest(prop.id, programs_rows[0].id, Response(),
                              db=db, current_user=manager)
        assert exc.value.status_code == 404
        programs_rows[0].is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_interest(prop.id, programs_rows[0].id, Response(),
                              db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert db.query(Lease).count() == 0 and db.query(GLTransaction).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()
