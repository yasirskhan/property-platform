"""Unit directory is an explicitly scoped inventory, not an occupancy claim."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.services import unit_directory
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "property.unit_directory"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Unit Directory One", slug="unit-dir-one")
    other = Organization(name="Unit Directory Other", slug="unit-dir-other")
    db.add_all((org, other)); db.flush()
    def user(o, role, name):
        x = User(organization_id=o.id, role=role, first_name=name,
                 last_name="Unitdir", email=f"{name.lower()}@unitdir.example",
                 hashed_password="x", is_active=True)
        db.add(x); db.flush(); return x
    admin = user(org, UserRole.ADMIN, "Admin")
    manager = user(org, UserRole.MANAGER, "Manager")
    tenant = user(org, UserRole.TENANT, "Tenant")
    other_admin = user(other, UserRole.ADMIN, "Other")
    def prop(o, name):
        p = Property(organization_id=o.id, name=name,
                     address_line1="1 Unit St", city="Cleveland",
                     state="OH", zip_code="44113", is_active=True)
        db.add(p); db.flush(); return p
    visible = prop(org, "=Visible")
    hidden = prop(org, "Hidden")
    foreign = prop(other, "Foreign")
    db.add(PropertyAssignment(
        property_id=visible.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def unit(prop_, number, *, active=True):
        x = Unit(
            property_id=prop_.id, unit_number=number,
            bedrooms=2, bathrooms=Decimal("1.5"),
            square_feet=850, monthly_rent=Decimal("1250.00"),
            security_deposit=Decimal("500.00"),
            pet_deposit=Decimal("0.00"), pet_rent=None,
            is_available=False, is_listed=True, is_active=active,
            available_from=date(2026, 10, 1),
        )
        db.add(x); db.flush(); return x
    first = unit(visible, "=A")
    inactive = unit(visible, "B", active=False)
    deleted = unit(visible, "C")
    deleted.deleted_at = datetime.utcnow()
    another = unit(hidden, "D")
    outside = unit(foreign, "Z")
    db.commit()
    return admin, manager, tenant, other_admin, visible, hidden, foreign, first, inactive, deleted, another, outside


def _payload(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, report_key=KEY,
        current_user=user, parameters=params,
    )


def test_recorded_unit_layout_and_flags_do_not_claim_vacancy_or_cash(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other_admin, visible, hidden, foreign, first, inactive, deleted, another, outside = _seed(db)
        monkeypatch.setattr(unit_directory, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        result = _payload(db, admin)
        assert len(result.rows) == 2
        row = next(row for row in result.rows if row[-1] == first.id)
        assert row[0:5] == ("=Visible", "=A", 2, Decimal("1.5"), 850)
        assert row[5:9] == (Decimal("1250"), Decimal("500"), Decimal("0"), "")
        assert row[9:12] == ("NO", "YES", date(2026, 10, 1))
        assert row[12] == visible.id
        assert db.query(GLTransaction).count() == before
        csv = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=Visible" in csv and "'=A" in csv
        assert "Foreign" not in csv and "Hidden" in csv
        assert "vacancy" in result.title.lower()
        assert "Collected" not in " ".join(result.headers)
    finally:
        db.close(); engine.dispose()


def test_manager_scope_inactive_filters_and_permissions(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other_admin, visible, hidden, foreign, first, inactive, deleted, another, outside = _seed(db)
        monkeypatch.setattr(unit_directory, "permission_allows_user", lambda *a, **k: True)
        assert [row[-1] for row in _payload(db, manager).rows] == [first.id]
        assert [row[-1] for row in _payload(db, admin, property_id=hidden.id).rows] == [another.id]
        for prop in (hidden, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=prop.id)
        for user in (tenant, other_admin):
            with pytest.raises(ReportDeliveryError):
                _payload(db, user, property_id=visible.id)
        for params in ({"sql": "select"}, {"property_id": -1}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        monkeypatch.setattr(unit_directory, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.UNITS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(unit_directory, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON" and item.href == "/dashboard/reporting/unit-directory"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PROPERTIES.UNITS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={})
        response = Response()
        preview = report_router.preview_unit_directory(req, response, db=db, current_user=admin)
        assert preview["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Configured Monthly Rent" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        emailed = report_router.email_report(
            KEY, report_router.ReportEmailIn(recipient="admin@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert emailed.sent and b"Available Flag" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_unit_directory(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
