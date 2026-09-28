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
from app.models.property import Property, PropertyAssignment, Unit
from app.models.unit_inspection import UnitInspectionRecord
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as programs, affordable_evidence as api
from app.services import unit_inspections
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



def test_program_inspection_summary_reuses_inspection_scope_not_hqs(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, foreign_prop), (program, other_program, foreign_program) = _seed(db)
        units = []
        for property_, name in ((prop, "A"), (other, "B"), (foreign_prop, "C")):
            unit = Unit(property_id=property_.id, unit_number=name, is_active=True)
            db.add(unit); units.append(unit)
        db.flush()
        for unit, property_ in ((units[0], prop), (units[0], prop),
                                 (units[1], other), (units[2], foreign_prop)):
            db.add(UnitInspectionRecord(
                organization_id=property_.organization_id, property_id=property_.id,
                unit_id=unit.id, inspection_date=date(2026, 9, 5),
                recorded_condition="ATTENTION_NEEDED",
                findings="Sensitive findings must not be in summary",
                recorded_by_id=admin.id,
            ))
        db.commit()
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        response = Response()
        summary = api.recorded_inspection_summary(
            prop.id, program.id, response, db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert summary.total_recorded == 2
        assert summary.latest_recorded_on == date(2026, 9, 5)
        assert "findings" not in summary.model_dump()
        assert "unit_id" not in summary.model_dump()
        assert api.recorded_inspection_summary(
            prop.id, program.id, Response(), db=db, current_user=manager,
        ).total_recorded == 2
        assert api.recorded_inspection_summary(
            other.id, other_program.id, Response(), db=db, current_user=admin,
        ).total_recorded == 1
        for actor in (owner, tenant):
            with pytest.raises(HTTPException) as exc:
                api.recorded_inspection_summary(
                    prop.id, program.id, Response(), db=db, current_user=actor,
                )
            assert exc.value.status_code == 403
        for actor, p, item in (
            (manager, other, other_program), (foreign, prop, program),
            (admin, prop, foreign_program),
        ):
            with pytest.raises(HTTPException) as exc:
                api.recorded_inspection_summary(p.id, item.id, Response(),
                                                db=db, current_user=actor)
            assert exc.value.status_code == 404
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.recorded_inspection_summary(
                prop.id, program.id, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        assert db.query(UnitInspectionRecord).count() == 4
        assert db.query(AffordableEvidence).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_inspection_summary_excludes_disabled_units_and_archived_program(monkeypatch):
    db, engine = _db()
    try:
        (admin, *_), (prop, _, _), (program, _, _) = _seed(db)
        unit = Unit(property_id=prop.id, unit_number="D", is_active=False)
        db.add(unit); db.flush()
        db.add(UnitInspectionRecord(
            organization_id=prop.organization_id, property_id=prop.id,
            unit_id=unit.id, inspection_date=date(2026, 9, 10),
            recorded_condition="ATTENTION_NEEDED", findings="private",
        ))
        db.commit()
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        summary = api.recorded_inspection_summary(
            prop.id, program.id, Response(), db=db, current_user=admin,
        )
        assert summary.total_recorded == 0 and summary.latest_recorded_on is None
        unit.is_active = True
        db.flush()
        assert api.recorded_inspection_summary(
            prop.id, program.id, Response(), db=db, current_user=admin,
        ).total_recorded == 1
        program.is_active = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.recorded_inspection_summary(
                prop.id, program.id, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_staff_public_agency_guidance_provenance_is_scoped_unverified_and_safe():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, unassigned, _), (program, other_program, _) = _seed(db)
        url = "https://www.hud.gov/program_offices/public_indian_housing"
        data = AffordableEvidenceIn(
            category="AGENCY_GUIDANCE", status="REFERENCE_IDENTIFIED",
            source_url=url, source_checked_on=date(2026, 9, 28),
        )
        saved = api.save_evidence(prop.id, program.id, data, db=db, current_user=admin)
        assert saved.source_url == url
        assert saved.source_checked_on == date(2026, 9, 28)
        read = api.list_evidence(prop.id, program.id, Response(),
                                 db=db, current_user=manager)
        assert read[0].source_url == url
        assert "agency_verified" not in read[0].model_dump()
        assert "eligibility" not in read[0].model_dump()
        # Link is staff-entered metadata only, never logged as sensitive content.
        logs = db.query(AuditLog).filter_by(entity_type="affordable_evidence").all()
        assert len(logs) == 1 and url not in (logs[0].new_value or "")
        for actor, property_, record in (
            (foreign, prop, program), (manager, unassigned, other_program),
        ):
            with pytest.raises(HTTPException):
                api.list_evidence(property_.id, record.id, Response(),
                                  db=db, current_user=actor)
        removed = api.save_evidence(
            prop.id, program.id, _payload(status="NOT_RECORDED"),
            db=db, current_user=owner,
        )
        assert removed.source_url is None and removed.source_checked_on is None
        for model in (GLTransaction, Charge, Lease):
            assert db.query(model).count() == 0
    finally:
        db.close(); engine.dispose()


def test_public_guidance_reference_validation_rejects_unsafe_and_false_certifications():
    def check(url, category="AGENCY_GUIDANCE", status="REFERENCE_IDENTIFIED",
              checked=date(2026, 9, 28)):
        return AffordableEvidenceIn(
            category=category, status=status, source_url=url,
            source_checked_on=checked,
        )
    for url in ("javascript:alert(1)", "http://www.hud.gov", "https://localhost/ref",
                "https://127.0.0.1/data", "https://user:secret@www.hud.gov/",
                "https://intranet.local/records", "https://agency.org:8443/ref",
                "https://agency.org/contains space", "https://example.com/" + "a"*510):
        with pytest.raises(ValueError):
            check(url)
    with pytest.raises(ValueError):
        check("https://www.hud.gov", category="PROGRAM_AGREEMENT")
    with pytest.raises(ValueError):
        check("https://www.hud.gov", status="NOT_RECORDED")
    with pytest.raises(ValueError):
        check("https://www.hud.gov", checked=date(2099, 1, 1))
    with pytest.raises(ValueError):
        AffordableEvidenceIn(category="AGENCY_GUIDANCE", status="REFERENCE_IDENTIFIED",
                             source_url=None, source_checked_on=date(2026, 9, 28))
    assert check(" https://www.hud.gov/a ").source_url == "https://www.hud.gov/a"
