"""Phase 3.7 inspections: explicit staff facts and strict tenant/org scope."""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.unit_inspection import UnitInspectionRecord
from app.models.user import Organization, User, UserRole
from app.routers import reporting as report_router
from app.routers import unit_inspections as inspection_router
from app.schemas.unit_inspection import UnitInspectionCreateIn
from app.services import unit_inspections
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "property.unit_inspection"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Inspection One", slug="inspection-one")
    other = Organization(name="Inspection Other", slug="inspection-other")
    db.add_all([one, other]); db.flush()
    def user(org, role, name):
        row = User(organization_id=org.id, role=role, first_name=name,
                   last_name="Inspection", email=f"{name.lower()}@inspection.example",
                   hashed_password="x", is_active=True)
        db.add(row); db.flush()
        return row
    admin = user(one, UserRole.ADMIN, "Admin")
    manager = user(one, UserRole.MANAGER, "Manager")
    tenant = user(one, UserRole.TENANT, "Tenant")
    foreign_admin = user(other, UserRole.ADMIN, "Foreign")
    def prop(org, name):
        row = Property(organization_id=org.id, name=name,
                       address_line1="1 Inspected Lane", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); db.flush()
        return row
    first = prop(one, "=Visible")
    hidden = prop(one, "Unassigned")
    foreign_prop = prop(other, "Secret")
    db.add(PropertyAssignment(
        property_id=first.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def unit(prop_, name):
        row = Unit(property_id=prop_.id, unit_number=name, is_active=True)
        db.add(row); db.flush()
        return row
    first_unit = unit(first, "=A")
    hidden_unit = unit(hidden, "B")
    foreign_unit = unit(foreign_prop, "C")
    db.commit()
    return admin, manager, tenant, foreign_admin, first, hidden, foreign_prop, first_unit, hidden_unit, foreign_unit


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id,
        report_key=KEY, parameters=params, current_user=actor,
    )


def _input(unit, condition="ATTENTION_NEEDED", findings="=Needs repair"):
    return UnitInspectionCreateIn(
        unit_id=unit.id, inspection_date=date.today(),
        recorded_condition=condition, findings=findings,
    )


def test_inspection_only_explicit_rows_audited_no_gl_writes(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, hidden, foreign, first_unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        assert _payload(db, admin).rows == ()
        before = db.query(GLTransaction).count()
        saved = inspection_router.create_inspection(
            _input(first_unit), Response(), db=db, current_user=admin,
        )
        assert saved.recorded_condition == "ATTENTION_NEEDED"
        assert saved.inspection_date == date.today()
        assert saved.recorded_by_id == admin.id
        assert db.query(UnitInspectionRecord).count() == 1
        assert db.query(AuditLog).filter_by(entity_type="unit_inspection_record").count() == 1
        assert db.query(GLTransaction).count() == before
        rows = _payload(db, admin).rows
        assert len(rows) == 1
        assert rows[0][:5] == ("=Visible", "=A", date.today(), "ATTENTION_NEEDED", "=Needs repair")
        assert rows[0][-1] == first_unit.id
        assert "'=Needs repair" in report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert "'=Visible" in report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert inspection_router.get_inspections(Response(), db=db, current_user=manager)[0].id == saved.id
    finally:
        db.close(); engine.dispose()


def test_scope_foreign_unit_assignment_role_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, hidden, foreign, first_unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        inspection_router.create_inspection(_input(first_unit), Response(), db=db, current_user=admin)
        for target in (hidden_unit, foreign_unit):
            with pytest.raises(HTTPException) as exc:
                inspection_router.create_inspection(
                    _input(target), Response(), db=db, current_user=manager,
                )
            assert exc.value.status_code == 404
        for actor in (tenant, other):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor, property_id=first.id)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _payload(db, manager, property_id=hidden.id)
        with pytest.raises(ReportDeliveryError, match="Unit not found"):
            _payload(db, manager, unit_id=foreign_unit.id)
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, sql="select")
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, date_from="2026-12-01", date_to="2026-01-01")
        monkeypatch.setattr(unit_inspections, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.UNITS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
        with pytest.raises(HTTPException) as exc:
            inspection_router.create_inspection(
                _input(first_unit), Response(), db=db, current_user=manager,
            )
        assert exc.value.status_code == 403
        assert db.query(UnitInspectionRecord).count() == 1
    finally:
        db.close(); engine.dispose()


def test_dates_and_inactive_unit_rejected(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, *_ = _seed(db)
        unit = db.query(Unit).first()
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        with pytest.raises(ValueError):
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today() + timedelta(days=1),
                recorded_condition="SATISFACTORY",
            )
        with pytest.raises(ValueError):
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today(),
                recorded_condition="BAD",
            )
        unit.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            inspection_router.create_inspection(_input(unit), Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, _, _, unit, _, _ = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        inspection_router.create_inspection(_input(unit), Response(), db=db, current_user=admin)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/unit-inspections"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PROPERTIES.UNITS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={"property_id": str(first.id)})
        resp = Response()
        preview = report_router.preview_unit_inspections(req, resp, db=db, current_user=admin)
        assert preview["total"] == 1
        assert resp.headers["cache-control"] == "no-store"
        csv = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"staff-recorded" in csv.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={"property_id": first.id},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"Needs repair" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_unit_inspections(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
