"""Manually recorded program labels must not certify HUD/LIHTC eligibility."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.affordable_program import AffordableProgram
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as api
from app.schemas.affordable_program import AffordableProgramIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Affordable One", slug="affordable-one")
    b = Organization(name="Affordable Two", slug="affordable-two")
    db.add_all([a, b]); db.flush()
    users = []
    for org, role, name in (
        (a, UserRole.ADMIN, "admin"), (a, UserRole.OWNER, "owner"),
        (a, UserRole.MANAGER, "manager"), (a, UserRole.TENANT, "tenant"),
        (b, UserRole.ADMIN, "foreign"),
    ):
        user = User(organization_id=org.id, role=role,
                    email=f"affordable-{name}@example.com",
                    first_name=name, last_name="Program",
                    hashed_password="x", is_active=True)
        db.add(user); users.append(user)
    db.flush()
    props = []
    for org, name in ((a, "Assigned"), (a, "Unassigned"), (b, "Foreign")):
        prop = Property(
            organization_id=org.id, name=name, address_line1="20 Main",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    return users, props


@pytest.fixture(autouse=True)
def features(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=api.FEATURE_KEY, allowed=True),
    ])


def _payload(**kwargs):
    data = {"program_type": "LIHTC", "label": "Building A"}
    data.update(kwargs)
    return AffordableProgramIn(**data)


def test_property_program_lifecycle_scoped_and_not_compliance_certification():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        created = api.create_program(assigned.id, _payload(), db=db, current_user=admin)
        assert created.property_id == assigned.id and created.program_type == "LIHTC"
        listed = api.list_programs(assigned.id, Response(), db=db, current_user=manager)
        assert [x.id for x in listed] == [created.id]
        assert api.list_programs(unassigned.id, Response(), db=db, current_user=owner) == []
        for actor, prop in ((manager, unassigned), (manager, other), (foreign, assigned)):
            with pytest.raises(HTTPException) as exc:
                api.list_programs(prop.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_program(assigned.id, _payload(label="No access"), db=db, current_user=actor)
            assert exc.value.status_code == 403
        update = api.update_program(
            assigned.id, created.id,
            _payload(program_type="SECTION_8_PROJECT_BASED", agency_name="Recorded agency"),
            db=db, current_user=owner,
        )
        assert update.program_type == "SECTION_8_PROJECT_BASED"
        with pytest.raises(HTTPException) as exc:
            api.update_program(other.id, created.id, _payload(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        api.archive_program(assigned.id, created.id, db=db, current_user=admin)
        assert api.list_programs(assigned.id, Response(), db=db, current_user=admin) == []
        assert db.query(AffordableProgram).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "affordable_program").count() == 3
        assert db.query(GLTransaction).count() == 0 and db.query(Charge).count() == 0
        assert "eligibility" not in update.__table__.columns
    finally:
        db.close(); engine.dispose()


def test_program_duplicate_period_validation_and_authorization_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        api.create_program(assigned.id, _payload(), db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.create_program(assigned.id, _payload(), db=db, current_user=admin)
        assert exc.value.status_code == 409
        with pytest.raises(ValueError):
            _payload(recorded_start=date(2026, 10, 1), recorded_end=date(2026, 9, 1))
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.list_programs(assigned.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=api.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_programs(assigned.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert db.query(AffordableProgram).count() == 1
    finally:
        db.close(); engine.dispose()


def test_program_no_store_and_inactive_property_manager_assignment():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        r = Response()
        api.list_programs(assigned.id, r, db=db, current_user=admin)
        assert r.headers["cache-control"] == "no-store"
        assignment = db.query(PropertyAssignment).filter(
            PropertyAssignment.property_id == assigned.id,
            PropertyAssignment.user_id == manager.id,
        ).one()
        assignment.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_programs(assigned.id, Response(), db=db, current_user=manager)
        assert exc.value.status_code == 404
        assigned.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.create_program(assigned.id, _payload(label="After deactivation"),
                               db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
