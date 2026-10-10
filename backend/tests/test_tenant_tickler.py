"""Tenant Tickler: latest genuine lease event with protected contact scope."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.entity_note import EntityNote
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "tenant.tickler"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Tickler One", slug="tickler-one")
    b = Organization(name="Tickler Two", slug="tickler-two")
    db.add_all([a, b])
    db.flush()
    def user(org, role, name):
        u = User(
            organization_id=org.id, role=role,
            email=f"{name.lower().replace('=', 'f')}@tickler.example",
            first_name=name, last_name="Test",
            hashed_password="x", is_active=True,
        )
        db.add(u)
        db.flush()
        return u
    admin = user(a, UserRole.ADMIN, "Admin")
    manager = user(a, UserRole.MANAGER, "Manager")
    tenant = user(a, UserRole.TENANT, "=Formula")
    idle = user(a, UserRole.TENANT, "Idle")
    foreign_tenant = user(b, UserRole.TENANT, "Foreign")
    def prop(org, name):
        p = Property(
            organization_id=org.id, name=name, address_line1="1 Test Ave",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(p)
        db.flush()
        return p
    assigned = prop(a, "Assigned")
    unassigned = prop(a, "Unassigned")
    private = prop(b, "Private")
    db.add(PropertyAssignment(
        property_id=assigned.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.flush()
    def lease(p, who, num, days_ago):
        unit = Unit(property_id=p.id, unit_number=num, is_active=True)
        db.add(unit)
        db.flush()
        stamp = datetime.utcnow() - timedelta(days=days_ago)
        l = Lease(
            unit_id=unit.id, tenant_id=who.id,
            start_date=date.today() - timedelta(days=200),
            end_date=date.today() + timedelta(days=300),
            monthly_rent=1000, security_deposit=500,
            status=LeaseStatus.ACTIVE, created_at=stamp, updated_at=stamp,
        )
        db.add(l)
        db.flush()
        return l
    old = lease(assigned, tenant, "A", 10)
    recent = lease(unassigned, tenant, "B", 5)
    private_lease = lease(private, foreign_tenant, "Z", 1)
    db.add(EntityNote(
        organization_id=a.id, entity_type="leases", entity_id=old.id,
        body="Private lease memo should NEVER appear in the report",
        created_at=datetime.utcnow() - timedelta(days=1),
        created_by_id=admin.id,
    ))
    db.add(EntityNote(
        organization_id=b.id, entity_type="leases", entity_id=private_lease.id,
        body="Another organization's secret",
        created_at=datetime.utcnow(),
    ))
    db.commit()
    return admin, manager, tenant, idle, foreign_tenant, assigned, unassigned, private, old, recent


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, report_key=KEY,
        parameters=params, current_user=user,
    )


def test_latest_real_note_event_is_scoped_and_redacted():
    db, engine = _session()
    try:
        admin, manager, tenant, idle, other, assigned, unassigned, private, old, recent = _seed(db)
        rows = _report(db, admin).rows
        assert len(rows) == 2
        item = next(row for row in rows if row[0] == tenant.id)
        assert item[6] == old.id
        assert item[10] == "Lease note recorded"
        assert item[11] != ""
        assert item[8] == old.start_date and item[9] == old.end_date
        assert any(row[0] == idle.id and row[10] == "No eligible recorded lease event" for row in rows)
        text = report_csv_bytes(_report(db, admin)).decode("utf-8-sig")
        assert "'=Formula Test" in text
        assert "Private lease memo" not in text
        assert "Another organization's secret" not in text
        assert "Foreign Test" not in text
    finally:
        db.close()
        engine.dispose()


def test_manager_only_assigned_lease_and_unassigned_contact_hidden():
    db, engine = _session()
    try:
        admin, manager, tenant, idle, other, assigned, unassigned, private, old, recent = _seed(db)
        rows = _report(db, manager).rows
        assert len(rows) == 1
        assert rows[0][0] == tenant.id
        assert rows[0][6] == old.id
        assert "Idle" not in str(rows)
        for p in (unassigned, private):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, manager, property_id=p.id)
        filtered = _report(db, admin, property_id=unassigned.id)
        assert filtered.rows[0][6] == recent.id
        assert filtered.rows[0][10] == "Lease record created"
        assert len(filtered.rows) == 1
    finally:
        db.close()
        engine.dispose()


def test_filters_unknown_property_disabled_actor_and_tenant_denied():
    db, engine = _session()
    try:
        admin, manager, tenant, idle, other, assigned, unassigned, private, old, recent = _seed(db)
        for params in ({"property_id": "abc"}, {"property_id": "-1"}, {"sql": "SELECT 1"}):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _report(db, admin, property_id=private.id)
        with pytest.raises(ReportDeliveryError):
            _report(db, tenant)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=admin.organization_id,
                report_key=KEY, parameters={},
            )
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError):
            _report(db, admin)
    finally:
        db.close()
        engine.dispose()


def test_catalog_preview_csv_email_and_permissions(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.tier == "STANDARD" and item.href == "/dashboard/reporting/tickler"
        assert router.REPORT_PERMISSIONS[KEY] == "LEASING"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)
            ],
        )
        req = SimpleNamespace(query_params={})
        response = Response()
        preview = router.preview_tenant_tickler(req, response, db=db, current_user=admin)
        assert preview["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        exported = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Last Recorded Event" in exported.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        result = router.email_report(
            KEY, router.ReportEmailIn(recipient="recipient@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert result.sent
        assert b"Last Recorded Event" in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)
            ],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_tenant_tickler(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(
            router, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL",
        )
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
