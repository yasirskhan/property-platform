"""Unit Vacancy Detail is candidate-only and reuses current recorded lease checks."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.services import rent_roll, unit_directory
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "property.unit_vacancy_detail"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    home = Organization(name="Vacancy One", slug="vacancy-one")
    other = Organization(name="Vacancy Two", slug="vacancy-two")
    db.add_all([home, other]); db.flush()
    def user(org, role, name):
        x = User(organization_id=org.id, role=role, first_name=name,
                 last_name="Vacancy", email=f"{name.lower()}@vacancy.example",
                 hashed_password="x", is_active=True)
        db.add(x); db.flush(); return x
    admin = user(home, UserRole.ADMIN, "Admin")
    manager = user(home, UserRole.MANAGER, "Manager")
    tenant = user(home, UserRole.TENANT, "Tenant")
    outsider = user(other, UserRole.ADMIN, "Outsider")
    def prop(org, name):
        p = Property(organization_id=org.id, name=name,
                     address_line1="1 Sample Lane", city="Cleveland",
                     state="OH", zip_code="44113", is_active=True)
        db.add(p); db.flush(); return p
    visible = prop(home, "=Visible")
    hidden = prop(home, "Unassigned")
    foreign = prop(other, "Secret")
    db.add(PropertyAssignment(
        property_id=visible.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def unit(p, number, available, *, active=True):
        u = Unit(property_id=p.id, unit_number=number,
                 monthly_rent=Decimal("1200.00"), is_available=available,
                 is_listed=not available, available_from=date(2026, 10, 1),
                 is_active=active)
        db.add(u); db.flush(); return u
    active = unit(visible, "=A", True)
    no_lease = unit(visible, "B", False)
    ended = unit(visible, "C", True)
    terminated = unit(visible, "D", False)
    disabled = unit(visible, "X", True, active=False)
    hidden_u = unit(hidden, "H", True)
    foreign_u = unit(foreign, "F", True)
    today = date.today()
    def lease(u, status, start, end):
        db.add(Lease(unit_id=u.id, tenant_id=tenant.id, status=status,
                     start_date=start, end_date=end,
                     monthly_rent=Decimal("1000.00"), security_deposit=0))
    lease(active, LeaseStatus.ACTIVE, today - timedelta(days=10), today + timedelta(days=10))
    lease(ended, LeaseStatus.ACTIVE, today - timedelta(days=90), today - timedelta(days=1))
    lease(terminated, LeaseStatus.TERMINATED, today - timedelta(days=10), today + timedelta(days=10))
    db.commit()
    return admin, manager, tenant, outsider, visible, hidden, foreign, active, no_lease, ended, terminated, disabled, hidden_u, foreign_u


def _permit(monkeypatch):
    monkeypatch.setattr(rent_roll, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(unit_directory, "permission_allows_user", lambda *a, **k: True)


def _payload(db, user, **parameters):
    return build_report_payload(
        db, organization_id=user.organization_id,
        report_key=KEY, current_user=user, parameters=parameters,
    )


def test_only_units_without_current_eligible_lease_and_flags_not_vacancy(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, visible, hidden, foreign, active, no_lease, ended, terminated, disabled, hidden_u, foreign_u = _seed(db)
        _permit(monkeypatch)
        before = db.query(GLTransaction).count()
        payload = _payload(db, admin)
        assert {row[-1] for row in payload.rows} == {no_lease.id, ended.id, terminated.id, hidden_u.id}
        assert all(row[-1] != active.id and row[-1] != disabled.id for row in payload.rows)
        flag_false = next(row for row in payload.rows if row[-1] == no_lease.id)
        assert flag_false[3:6] == ("NO", "YES", date(2026, 10, 1))
        assert "vacancy not verified" in flag_false[2]
        assert "physical vacancy NOT verified" in payload.title
        assert "collected" not in " ".join(payload.headers).lower()
        assert db.query(GLTransaction).count() == before
        csv = report_csv_bytes(payload).decode("utf-8-sig")
        assert "'=Visible" in csv
        assert "Secret" not in csv
    finally:
        db.close(); engine.dispose()


def test_manager_scope_foreign_probes_revocation_and_overlapping_lease(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, outsider, visible, hidden, foreign, active, no_lease, ended, terminated, disabled, hidden_u, foreign_u = _seed(db)
        _permit(monkeypatch)
        assert {row[-1] for row in _payload(db, manager).rows} == {no_lease.id, ended.id, terminated.id}
        for prop in (hidden, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=prop.id)
        for actor in (tenant, outsider):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, property_id=visible.id)
        for params in ({"sql": "select"}, {"property_id": "-2"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        db.add(Lease(
            unit_id=active.id, tenant_id=tenant.id, status=LeaseStatus.ACTIVE,
            start_date=date.today()-timedelta(days=1),
            end_date=date.today()+timedelta(days=1),
            monthly_rent=1200, security_deposit=0,
        ))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="Overlapping"):
            _payload(db, admin)
        monkeypatch.setattr(rent_roll, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
        _permit(monkeypatch)
        monkeypatch.setattr(unit_directory, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.UNITS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_export_email_and_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, _, _, visible, *_ = _seed(db)
        _permit(monkeypatch)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/unit-vacancy-detail"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PROPERTIES.UNITS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={"property_id": str(visible.id)})
        response = Response()
        preview = report_router.preview_unit_vacancy_detail(req, response, db=db, current_user=admin)
        assert preview["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Current Recorded Lease Association" in exported.body
        emailed = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: emailed.update(kwargs))
        sent = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={"property_id": visible.id},
            ), db=db, current_user=admin,
        )
        assert sent.sent and b"vacancy not verified" in emailed["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_unit_vacancy_detail(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
