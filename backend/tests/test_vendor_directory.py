"""Vendor directory cannot invent vendors from bills or leak tax records."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.services import vendor_directory
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "vendor.directory"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Vendor Dir One", slug="vendor-dir-one")
    other = Organization(name="Vendor Dir Two", slug="vendor-dir-two")
    db.add_all([org, other]); db.flush()
    def user(target, role, name, *, active=True):
        row = User(organization_id=target.id, role=role, first_name=name,
                   last_name="=Vendor", email=f"{name.lower()}@vendor-dir.example",
                   phone="216-555-0202", hashed_password="x", is_active=active)
        db.add(row); db.flush(); return row
    admin = user(org, UserRole.ADMIN, "Admin")
    owner = user(org, UserRole.OWNER, "Owner")
    manager = user(org, UserRole.MANAGER, "Manager")
    first = user(org, UserRole.VENDOR, "=First")
    second = user(org, UserRole.VENDOR, "Second")
    crew = user(org, UserRole.VENDOR_CREW, "VendorCrew")
    inactive = user(org, UserRole.VENDOR, "Inactive", active=False)
    deleted = user(org, UserRole.VENDOR, "Deleted")
    deleted.deleted_at = datetime.utcnow()
    tenant = user(org, UserRole.TENANT, "Tenant")
    foreign = user(other, UserRole.VENDOR, "Foreign")
    db.commit()
    return admin, owner, manager, first, second, crew, inactive, deleted, tenant, foreign


def _payload(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, current_user=user,
        report_key=KEY, parameters=params,
    )


def test_only_real_active_vendor_accounts_with_contact_fields(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, first, second, crew, inactive, deleted, tenant, foreign = _seed(db)
        monkeypatch.setattr(vendor_directory, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        report = _payload(db, admin)
        assert {row[0] for row in report.rows} == {first.id, second.id}
        assert {row[0] for row in _payload(db, owner).rows} == {first.id, second.id}
        assert len(report.headers) == 4
        assert all(row[3] == "216-555-0202" for row in report.rows)
        assert "tax" not in " ".join(report.headers).lower()
        assert db.query(GLTransaction).count() == before
        csv = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=First =Vendor" in csv
        assert "Foreign" not in csv and "VendorCrew" not in csv
        assert "123-45-6789" not in csv
    finally:
        db.close(); engine.dispose()


def test_unchanged_user_management_role_boundary_and_revocations(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, first, second, crew, inactive, deleted, tenant, foreign = _seed(db)
        monkeypatch.setattr(vendor_directory, "permission_allows_user", lambda *a, **k: True)
        for actor in (manager, tenant, first, crew):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor)
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, sql="SELECT * FROM tax_profiles")
        assert [row[0] for row in _payload(db, foreign).rows] == [foreign.id]
        monkeypatch.setattr(vendor_directory, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PEOPLE.VENDORS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(vendor_directory, "permission_allows_user", lambda *a, **k: True)
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_revoked_export(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, *_ = _seed(db)
        monkeypatch.setattr(vendor_directory, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/vendor-directory"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PEOPLE.VENDORS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={})
        response = Response()
        preview = report_router.preview_vendor_directory(req, response, db=db, current_user=admin)
        assert preview["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        response_csv = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Recorded Name" in response_csv.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"216-555-0202" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_vendor_directory(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
