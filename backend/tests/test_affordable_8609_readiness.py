"""Per-building 8609 references are staff metadata, never IRS certifications."""
from __future__ import annotations
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.affordable_program import AffordableProgram
from app.models.affordable_building import AffordableBuilding
from app.models.affordable_8609_readiness import Affordable8609Readiness
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as programs
from app.routers import affordable_8609_readiness as api
from app.schemas.affordable_8609_readiness import Affordable8609ReadinessIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
    monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=programs.FEATURE_KEY, allowed=True),
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one, two = Organization(name="Form Readiness One", slug="form-readiness-one"), Organization(name="Form Readiness Two", slug="form-readiness-two")
    db.add_all([one, two]); db.flush()
    users = []
    for org, role, label in (
        (one, UserRole.ADMIN, "admin"), (one, UserRole.OWNER, "owner"),
        (one, UserRole.MANAGER, "manager"), (one, UserRole.TENANT, "tenant"),
        (two, UserRole.ADMIN, "foreign"),
    ):
        user = User(organization_id=org.id, role=role, first_name=label,
                    last_name="Form", email=f"8609-{label}@example.com",
                    hashed_password="x", is_active=True)
        db.add(user); users.append(user)
    db.flush()
    props = []
    for org, name in ((one, "Assigned"), (one, "Unassigned"), (two, "Foreign")):
        p = Property(organization_id=org.id, name=name, address_line1="10 Main",
                     city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(p); props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id, user_id=users[2].id,
                              role=UserRole.MANAGER, is_active=True))
    programs_list, buildings = [], []
    for prop in props:
        pr = AffordableProgram(organization_id=prop.organization_id, property_id=prop.id,
                               program_type="LIHTC", label="Recorded LIHTC", is_active=True)
        db.add(pr); db.flush()
        building = AffordableBuilding(organization_id=prop.organization_id, property_id=prop.id,
                                     program_id=pr.id, building_label="A", agency_bin="OH-20-12345",
                                     is_active=True)
        db.add(building); db.flush()
        programs_list.append(pr); buildings.append(building)
    db.commit()
    return users, props, programs_list, buildings


def _value(status="REFERENCE_IDENTIFIED"):
    return Affordable8609ReadinessIn(status=status)


def test_8609_reference_lifecycle_audit_and_nonmutation():
    db, engine = _db()
    try:
        (admin, owner, manager, *_), (prop, _, _), (program, _, _), (building, _, _) = _seed(db)
        result = Response()
        blank = api.get_readiness(prop.id, program.id, building.id, result,
                                  db=db, current_user=manager)
        assert result.headers["cache-control"] == "no-store"
        assert blank.status == "NOT_RECORDED"
        assert db.query(Affordable8609Readiness).count() == 0
        saved = api.save_readiness(prop.id, program.id, building.id, _value(),
                                   db=db, current_user=admin)
        assert saved.status == "REFERENCE_IDENTIFIED" and saved.building_id == building.id
        changed = api.save_readiness(prop.id, program.id, building.id, _value("FOLLOW_UP_NEEDED"),
                                     db=db, current_user=owner)
        assert changed.status == "FOLLOW_UP_NEEDED"
        assert api.get_readiness(prop.id, program.id, building.id, Response(),
                                 db=db, current_user=manager).status == "FOLLOW_UP_NEEDED"
        assert db.query(Affordable8609Readiness).count() == 1
        assert db.query(AuditLog).filter_by(entity_type="affordable_8609_readiness").count() == 2
        for cls in (Lease, Charge, GLTransaction):
            assert db.query(cls).count() == 0
        assert not hasattr(saved, "tax_credit") and not hasattr(saved, "certified")
    finally:
        db.close(); engine.dispose()


def test_8609_reference_scope_and_write_guards():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), props, programs_list, buildings = _seed(db)
        for actor, ix in ((manager, 1), (manager, 2), (foreign, 0), (admin, 2)):
            with pytest.raises(HTTPException) as exc:
                api.get_readiness(props[ix].id, programs_list[ix].id, buildings[ix].id,
                                  Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404
        # An org administrator may access another property inside the same organization.
        assert api.get_readiness(props[1].id, programs_list[1].id, buildings[1].id,
                                 Response(), db=db, current_user=admin).status == "NOT_RECORDED"
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.save_readiness(props[0].id, programs_list[0].id, buildings[0].id,
                                   _value(), db=db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.get_readiness(props[0].id, programs_list[0].id, buildings[1].id,
                              Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        buildings[0].is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.get_readiness(props[0].id, programs_list[0].id, buildings[0].id,
                              Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_8609_no_generic_attachment_and_permission_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, _, manager, *_), (prop, _, _), (program, _, _), (building, _, _) = _seed(db)
        with pytest.raises(ValueError):
            _value("AGENCY_CERTIFIED")
        with pytest.raises(HTTPException) as exc:
            _model_for_table("affordable_lihtc_8609_readiness")
        assert exc.value.status_code == 404
        monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.get_readiness(prop.id, program.id, building.id,
                              Response(), db=db, current_user=manager)
        assert exc.value.status_code == 403
        monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=programs.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.get_readiness(prop.id, program.id, building.id,
                              Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()
