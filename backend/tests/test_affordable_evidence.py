"""Staff-only affordable evidence index: no certifications or protected documents."""
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
from app.models.affordable_evidence import AffordableEvidence
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as programs, affordable_evidence as api
from app.schemas.affordable_evidence import AffordableEvidenceIn
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
    org, other = Organization(name="Evidence One", slug="evidence-one"), Organization(name="Evidence Other", slug="evidence-other")
    db.add_all([org, other]); db.flush()
    users = []
    for o, role, label in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        u = User(organization_id=o.id, role=role, first_name=label,
                 last_name="Evidence", email=f"evidence-{label}@example.com",
                 hashed_password="x", is_active=True)
        db.add(u); users.append(u)
    db.flush()
    props = []
    for o, label in ((org, "Assigned"), (org, "Unassigned"), (other, "Foreign")):
        p = Property(organization_id=o.id, name=label, address_line1="10 Main",
                     city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(p); props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id, user_id=users[2].id,
                              role=UserRole.MANAGER, is_active=True))
    rows = []
    for p in props:
        row = AffordableProgram(organization_id=p.organization_id, property_id=p.id,
                                program_type="LIHTC", label="Index", is_active=True)
        db.add(row); rows.append(row)
    db.commit()
    return users, props, rows


def _payload(category="AGENCY_GUIDANCE", status="REFERENCE_IDENTIFIED", due=None):
    return AffordableEvidenceIn(category=category, status=status, staff_follow_up_on=due)


def test_fixed_categories_staff_lifecycle_audit_and_nonmutation():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (p, _, _), (program, _, _) = _seed(db)
        reply = Response()
        blank = api.list_evidence(p.id, program.id, reply, db=db, current_user=manager)
        assert reply.headers["cache-control"] == "no-store"
        assert len(blank) == 4 and all(x.status == "NOT_RECORDED" for x in blank)
        assert db.query(AffordableEvidence).count() == 0
        saved = api.save_evidence(p.id, program.id, _payload(due=date(2026, 11, 15)),
                                  db=db, current_user=admin)
        assert saved.category == "AGENCY_GUIDANCE" and saved.staff_follow_up_on == date(2026, 11, 15)
        changed = api.save_evidence(p.id, program.id, _payload(status="FOLLOW_UP_NEEDED"),
                                    db=db, current_user=owner)
        assert changed.status == "FOLLOW_UP_NEEDED"
        assert db.query(AffordableEvidence).count() == 1
        listed = api.list_evidence(p.id, program.id, Response(), db=db, current_user=manager)
        assert listed[0].status == "FOLLOW_UP_NEEDED"
        assert listed[0].staff_follow_up_on is None
        assert db.query(AuditLog).filter_by(entity_type="affordable_evidence").count() == 2
        for model in (Charge, GLTransaction, Lease):
            assert db.query(model).count() == 0
        assert not hasattr(saved, "eligibility") and not hasattr(saved, "approved")
    finally:
        db.close(); engine.dispose()


def test_tenant_manager_cross_org_and_program_probes():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (p, unassigned, foreign_prop), (program, other_program, foreign_program) = _seed(db)
        for actor, prop, item in (
            (manager, unassigned, other_program), (manager, foreign_prop, foreign_program),
            (foreign, p, program), (admin, p, other_program),
        ):
            with pytest.raises(HTTPException) as exc:
                api.list_evidence(prop.id, item.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.save_evidence(p.id, program.id, _payload(), db=db, current_user=actor)
            assert exc.value.status_code == 403
        for actor in (tenant,):
            with pytest.raises(HTTPException):
                api.list_evidence(p.id, program.id, Response(), db=db, current_user=actor)
    finally:
        db.close(); engine.dispose()


def test_release_permission_archival_validation_and_generic_target_denial(monkeypatch):
    db, engine = _db()
    try:
        (admin, _, manager, _, _), (p, _, _), (program, _, _) = _seed(db)
        with pytest.raises(ValueError):
            _payload(category="INCOME_CERTIFICATION")
        with pytest.raises(ValueError):
            _payload(status="CERTIFIED")
        with pytest.raises(HTTPException) as exc:
            _model_for_table("affordable_program_evidence")
        assert exc.value.status_code == 404
        monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.list_evidence(p.id, program.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=programs.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_evidence(p.id, program.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=programs.FEATURE_KEY, allowed=True),
        ])
        program.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_evidence(p.id, program.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()
