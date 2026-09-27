"""Owner Directory excludes foreign, unassigned and sensitive identity data."""
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
from app.models.property import Property, PropertyAssignment, PropertyOwner
from app.models.user import Organization, User, UserRole
from app.services import owner_directory
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "owner.directory"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Owner Directory One", slug="owner-dir-one")
    second = Organization(name="Owner Directory Two", slug="owner-dir-two")
    db.add_all((first, second)); db.flush()
    def user(org, role, name, *, active=True):
        x = User(organization_id=org.id, role=role, first_name=name,
                 last_name="=Family", email=f"{name.lower()}@ownerdir.example",
                 phone="216-555-0101", hashed_password="x", is_active=active)
        db.add(x); db.flush(); return x
    admin = user(first, UserRole.ADMIN, "Admin")
    manager = user(first, UserRole.MANAGER, "Manager")
    owner1 = user(first, UserRole.OWNER, "Visible")
    owner2 = user(first, UserRole.OWNER, "Hidden")
    inactive = user(first, UserRole.OWNER, "Inactive", active=False)
    deleted = user(first, UserRole.OWNER, "Deleted")
    deleted.deleted_at = datetime.utcnow()
    tenant = user(first, UserRole.TENANT, "Tenant")
    foreign = user(second, UserRole.OWNER, "Foreign")
    def property_(org, name):
        p = Property(organization_id=org.id, name=name,
                     address_line1="100 Test St", city="Cleveland",
                     state="OH", zip_code="44113", is_active=True)
        db.add(p); db.flush(); return p
    visible = property_(first, "Visible")
    hidden = property_(first, "Hidden")
    foreign_property = property_(second, "Foreign")
    db.add(PropertyAssignment(
        property_id=visible.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def owner_link(org, prop, person):
        db.add(PropertyOwner(organization_id=org.id,
                             property_id=prop.id, user_id=person.id,
                             ownership_pct=100, is_active=True))
    owner_link(first, visible, owner1)
    owner_link(first, hidden, owner2)
    owner_link(second, foreign_property, foreign)
    db.commit()
    return admin, manager, owner1, owner2, inactive, deleted, tenant, foreign


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id,
        report_key=KEY, current_user=actor, parameters=params,
    )


def test_owner_directory_only_stored_contacts_and_owner_self_scope(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, owner1, owner2, inactive, deleted, tenant, foreign = _seed(db)
        monkeypatch.setattr(owner_directory, "permission_allows_user", lambda *a, **k: True)
        owner1.first_name = "=Visible"
        db.commit()
        before = db.query(GLTransaction).count()
        rows = _payload(db, admin).rows
        assert {row[0] for row in rows} == {owner1.id, owner2.id}
        assert all(len(row) == 4 for row in rows)
        assert all(row[3] == "216-555-0101" for row in rows)
        assert [row[0] for row in _payload(db, owner1).rows] == [owner1.id]
        assert [row[0] for row in _payload(db, owner2).rows] == [owner2.id]
        assert "tax" not in " ".join(_payload(db, admin).headers).lower()
        assert db.query(GLTransaction).count() == before
        csv = report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert "'=Visible =Family" in csv and "Foreign" not in csv
        assert "123-45-6789" not in csv
    finally:
        db.close(); engine.dispose()


def test_owner_directory_does_not_widen_manager_user_detail_access(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, owner1, owner2, inactive, deleted, tenant, foreign = _seed(db)
        monkeypatch.setattr(owner_directory, "permission_allows_user", lambda *a, **k: True)
        # Existing /users/{id} deliberately limits manager detail to crew;
        # owner-directory must not widen that policy via a menu grant.
        for actor in (manager, tenant):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor)
        assert [row[0] for row in _payload(db, foreign).rows] == [foreign.id]
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, sql="SELECT * FROM tax_profiles")
        monkeypatch.setattr(owner_directory, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PEOPLE.OWNERS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(owner_directory, "permission_allows_user", lambda *a, **k: True)
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_rechecks(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, owner1, *_ = _seed(db)
        monkeypatch.setattr(owner_directory, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/owner-directory"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PEOPLE.OWNERS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={})
        response = Response()
        preview = report_router.preview_owner_directory(req, response, db=db, current_user=admin)
        assert preview["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Recorded Name" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"216-555-0101" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_owner_directory(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
