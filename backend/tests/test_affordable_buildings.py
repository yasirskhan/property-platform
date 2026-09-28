"""Program-scoped staff BIN registry is NOT Form 8609 or credit calculation."""
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
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as programs, affordable_buildings as api
from app.schemas.affordable_building import AffordableBuildingIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def access(monkeypatch):
    monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=programs.FEATURE_KEY, allowed=True),
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one, two = Organization(name="BIN One", slug="bin-one"), Organization(name="BIN Two", slug="bin-two")
    db.add_all([one, two]); db.flush()
    users = []
    for org, role, label in (
        (one, UserRole.ADMIN, "admin"), (one, UserRole.OWNER, "owner"),
        (one, UserRole.MANAGER, "manager"), (one, UserRole.TENANT, "tenant"),
        (two, UserRole.ADMIN, "foreign"),
    ):
        u = User(organization_id=org.id, role=role, first_name=label,
                 last_name="Building", email=f"bin-{label}@example.com",
                 hashed_password="x", is_active=True)
        db.add(u); users.append(u)
    db.flush()
    props = []
    for org, label in ((one, "Assigned"), (one, "Unassigned"), (two, "Foreign")):
        p = Property(organization_id=org.id, name=label, address_line1="10 Main",
                     city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(p); props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id, user_id=users[2].id,
                              role=UserRole.MANAGER, is_active=True))
    rows = []
    for p in props:
        program = AffordableProgram(organization_id=p.organization_id, property_id=p.id,
                                    program_type="LIHTC", label="Recorded tax credit", is_active=True)
        db.add(program); rows.append(program)
    db.commit()
    return users, props, rows


def _input(bin="OH-20-12345", label="Building 1"):
    return AffordableBuildingIn(building_label=label, agency_bin=bin)


def test_lihtc_bin_lifecycle_org_scope_and_nonmutation():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, foreign_prop), (program, other_program, foreign_program) = _seed(db)
        made = api.record_building(prop.id, program.id, _input(),
                                   db=db, current_user=admin)
        assert made.agency_bin == "OH-20-12345"
        assert api.list_buildings(prop.id, program.id, Response(),
                                  db=db, current_user=manager)[0].id == made.id
        another = api.record_building(prop.id, program.id, _input("OH-20-12346", "Building 2"),
                                      db=db, current_user=owner)
        assert len(api.list_buildings(prop.id, program.id, Response(), db=db, current_user=admin)) == 2
        with pytest.raises(HTTPException) as exc:
            api.record_building(prop.id, program.id, _input(), db=db, current_user=admin)
        assert exc.value.status_code == 409
        api.archive_building(prop.id, program.id, made.id, db=db, current_user=owner)
        assert len(api.list_buildings(prop.id, program.id, Response(), db=db, current_user=admin)) == 1
        restored = api.record_building(prop.id, program.id, _input(label="Restored"),
                                       db=db, current_user=admin)
        assert restored.id == made.id and restored.building_label == "Restored"
        assert db.query(AffordableBuilding).count() == 2
        assert db.query(AuditLog).filter_by(entity_type="affordable_lihtc_building").count() == 4
        for model in (Charge, GLTransaction, Lease):
            assert db.query(model).count() == 0
        assert "tax_credit" not in made.__table__.columns
        assert "tin" not in made.__table__.columns
        assert another.agency_bin.endswith("12346")
    finally:
        db.close(); engine.dispose()


def test_cross_property_manager_and_other_org_bin_probes():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, foreign_prop), (program, other_program, foreign_program) = _seed(db)
        one = api.record_building(prop.id, program.id, _input(),
                                  db=db, current_user=admin)
        for actor, p, prog in (
            (manager, other, other_program), (manager, foreign_prop, foreign_program),
            (foreign, prop, program), (admin, prop, other_program),
        ):
            with pytest.raises(HTTPException) as exc:
                api.list_buildings(p.id, prog.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.record_building(prop.id, program.id, _input("OH-20-54321"), db=db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.archive_building(other.id, other_program.id, one.id, db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_only_active_lihtc_permissions_bin_shape_and_generic_target(monkeypatch):
    db, engine = _db()
    try:
        (admin, _, manager, _, _), (prop, _, _), (program, _, _) = _seed(db)
        for value in ("123456789", "A", "OH/20/12345"):
            with pytest.raises(ValueError):
                _input(value)
        assert _input(" oh-20-12345 ").agency_bin == "OH-20-12345"
        with pytest.raises(HTTPException) as exc:
            _model_for_table("affordable_lihtc_buildings")
        assert exc.value.status_code == 404
        program.program_type = "SECTION_8_VOUCHER"
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.record_building(prop.id, program.id, _input(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        program.program_type = "LIHTC"
        db.flush()
        monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.list_buildings(prop.id, program.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=programs.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_buildings(prop.id, program.id, Response(), db=db, current_user=manager)
        assert exc.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()
