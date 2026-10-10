"""Property directory: active-only physical metadata, scoped unit counts and delivery."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.services import property_directory
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)
from app.routers import reporting as report_router

KEY = "property.directory"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Directory One", slug="directory-one")
    other = Organization(name="Directory Other", slug="directory-other")
    db.add_all([org, other]); db.flush()
    def user(o, role, name):
        u = User(organization_id=o.id, role=role, first_name=name,
                 last_name="Directory", email=f"{name.lower()}@directory.example",
                 hashed_password="x", is_active=True)
        db.add(u); db.flush()
        return u
    admin = user(org, UserRole.ADMIN, "Admin")
    manager = user(org, UserRole.MANAGER, "Manager")
    tenant = user(org, UserRole.TENANT, "Tenant")
    foreign_admin = user(other, UserRole.ADMIN, "Foreign")
    def property_(o, name, kind):
        p = Property(
            organization_id=o.id, name=name, property_type=kind,
            address_line1="=123 Main Street", address_line2=None,
            city="Cleveland", state="OH", zip_code="44113",
            country="USA", year_built=1980, is_active=True,
        )
        db.add(p); db.flush()
        return p
    first = property_(org, "=First Property", PropertyType.MULTI_FAMILY)
    hidden = property_(org, "Hidden Property", PropertyType.SINGLE_FAMILY)
    outside = property_(other, "Foreign Property", PropertyType.APARTMENT)
    db.add(PropertyAssignment(
        property_id=first.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.flush()
    for p, number, active in (
        (first, "A", True), (first, "B", True),
        (first, "C", False), (hidden, "D", True),
        (outside, "E", True),
    ):
        db.add(Unit(property_id=p.id, unit_number=number,
                    monthly_rent=1200, is_active=active))
    db.commit()
    return admin, manager, tenant, foreign_admin, first, hidden, outside


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        parameters=params, current_user=actor,
    )


def test_directory_is_scoped_inventory_not_revenue_or_tenant_contacts(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, hidden, outside = _seed(db)
        monkeypatch.setattr(property_directory, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        report = _payload(db, admin)
        assert len(report.rows) == 2
        first_row = next(row for row in report.rows if row[0] == first.id)
        assert first_row[1:4] == ("=First Property", "multi_family", "=123 Main Street")
        assert first_row[9] == 2 and first_row[10] == 1980
        assert "rent" not in " ".join(report.headers).lower()
        assert "tenant" not in " ".join(report.headers).lower()
        assert db.query(GLTransaction).count() == before
        csv_text = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=First Property" in csv_text and "'=123 Main Street" in csv_text
        assert "Foreign Property" not in csv_text
        hidden.is_active = False
        db.commit()
        assert len(_payload(db, admin).rows) == 1
    finally:
        db.close(); engine.dispose()


def test_manager_scope_type_filter_foreign_id_and_permissions(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, hidden, outside = _seed(db)
        monkeypatch.setattr(property_directory, "permission_allows_user", lambda *a, **k: True)
        assert [r[0] for r in _payload(db, manager).rows] == [first.id]
        assert len(_payload(db, admin, property_type="multi_family").rows) == 1
        assert _payload(db, admin, property_type="condo").rows == ()
        for p in (hidden, outside):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=p.id)
        for actor in (tenant, foreign_admin):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, property_id=first.id)
        for args in ({"sql": "select"}, {"property_id": -1},
                     {"property_type": "not_an_enum"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **args)
        monkeypatch.setattr(property_directory, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.ALL")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_export_email_no_store_and_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, *_ = _seed(db)
        monkeypatch.setattr(property_directory, "permission_allows_user", lambda *a, **k: True)
        item = next(item for item in REPORT_CATALOG if item.key == KEY)
        assert item.tier == "STANDARD" and item.href == "/dashboard/reporting/property-directory"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PROPERTIES.ALL"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={})
        response = Response()
        preview = report_router.preview_property_directory(req, response, db=db, current_user=admin)
        assert preview["total"] == 2 and response.headers["cache-control"] == "no-store"
        csv = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Active Unit Records" in csv.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        emailed = report_router.email_report(
            KEY, report_router.ReportEmailIn(recipient="staff@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert emailed.sent and b"Property Name" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_property_directory(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
