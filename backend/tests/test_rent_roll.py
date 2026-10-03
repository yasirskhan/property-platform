"""Current-record rent roll: never invent occupied units or collected cash."""
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
from app.services import rent_roll
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "property.rent_roll"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Rent Roll One", slug="rent-roll-one")
    other = Organization(name="Rent Roll Other", slug="rent-roll-other")
    db.add_all((org, other)); db.flush()

    def user(o, role, name):
        x = User(organization_id=o.id, role=role, first_name=name,
                 last_name="Rentroll", email=f"{name.lower()}@roll.example",
                 hashed_password="x", is_active=True)
        db.add(x); db.flush()
        return x
    admin = user(org, UserRole.ADMIN, "Admin")
    manager = user(org, UserRole.MANAGER, "Manager")
    tenant = user(org, UserRole.TENANT, "Tenant")
    foreign_admin = user(other, UserRole.ADMIN, "Foreign")
    foreign_tenant = user(other, UserRole.TENANT, "Outsider")

    def prop(o, name):
        p = Property(organization_id=o.id, name=name,
                     address_line1="1 Rent St", city="Cleveland",
                     state="OH", zip_code="44113", is_active=True)
        db.add(p); db.flush()
        return p
    visible = prop(org, "=Visible")
    hidden = prop(org, "Unassigned")
    outside = prop(other, "Secret")
    db.add(PropertyAssignment(
        property_id=visible.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def unit(p, number, rent=1000, active=True):
        x = Unit(property_id=p.id, unit_number=number,
                 monthly_rent=Decimal(rent), is_active=active)
        db.add(x); db.flush()
        return x
    occupied = unit(visible, "=A", 1500)
    no_lease = unit(visible, "B", 1100)
    expired = unit(visible, "C", 1200)
    disabled = unit(visible, "D", 999, active=False)
    hidden_unit = unit(hidden, "Z", 3000)
    foreign_unit = unit(outside, "X", 10000)
    today = date.today()
    def lease_(u, person, status, start, end, rent):
        x = Lease(unit_id=u.id, tenant_id=person.id, status=status,
                  start_date=start, end_date=end, monthly_rent=Decimal(rent),
                  security_deposit=Decimal(0))
        db.add(x); db.flush()
        return x
    lease_(occupied, tenant, LeaseStatus.ACTIVE,
           today-timedelta(days=30), today+timedelta(days=30), 1300)
    lease_(expired, tenant, LeaseStatus.ACTIVE,
           today-timedelta(days=90), today-timedelta(days=1), 1200)
    lease_(no_lease, tenant, LeaseStatus.TERMINATED,
           today-timedelta(days=30), today+timedelta(days=30), 1100)
    lease_(hidden_unit, tenant, LeaseStatus.ACTIVE,
           today-timedelta(days=30), today+timedelta(days=30), 3000)
    lease_(foreign_unit, foreign_tenant, LeaseStatus.ACTIVE,
           today-timedelta(days=30), today+timedelta(days=30), 10000)
    db.commit()
    return admin, manager, tenant, foreign_admin, foreign_tenant, visible, hidden, outside, occupied, no_lease, expired, disabled


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id,
        report_key=KEY, current_user=actor, parameters=params,
    )


def test_market_vs_contract_current_records_not_collections(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other_admin, foreign_tenant, visible, hidden, outside, occupied, no_lease, expired, disabled = _seed(db)
        monkeypatch.setattr(rent_roll, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        result = _payload(db, admin)
        assert len(result.rows) == 4
        first = next(row for row in result.rows if row[10] == occupied.id)
        assert first[0] == "=Visible" and first[1] == "=A"
        assert first[2] == "CURRENT RECORDED LEASE"
        assert first[3] == Decimal("1500") and first[4] == Decimal("1300")
        assert first[5] == "Tenant Rentroll" and first[8] != ""
        assert first[11] == tenant.id
        for unit_id in (no_lease.id, expired.id):
            row = next(row for row in result.rows if row[10] == unit_id)
            assert "vacancy not verified" in row[2]
            assert row[4] == "" and row[8] == "" and row[11] == ""
        assert all(row[10] != disabled.id for row in result.rows)
        assert db.query(GLTransaction).count() == before
        csv = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=Visible" in csv and "'=A" in csv
        assert "Secret" not in csv
        assert "Collected" not in " ".join(result.headers)
    finally:
        db.close(); engine.dispose()


def test_manager_scope_foreign_tenant_overlap_and_permissions(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other_admin, foreign_tenant, visible, hidden, outside, occupied, no_lease, expired, disabled = _seed(db)
        monkeypatch.setattr(rent_roll, "permission_allows_user", lambda *a, **k: True)
        assert len(_payload(db, manager).rows) == 3
        for prop in (hidden, outside):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=prop.id)
        for actor in (tenant, other_admin):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, property_id=visible.id)
        for params in ({"sql": "select"}, {"property_id": -1}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        today = date.today()
        db.add(Lease(
            unit_id=occupied.id, tenant_id=tenant.id,
            start_date=today-timedelta(days=1), end_date=today+timedelta(days=1),
            monthly_rent=1400, security_deposit=0, status=LeaseStatus.ACTIVE,
        ))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="Overlapping"):
            _payload(db, admin, property_id=visible.id)
        # Removing one lease leaves a deliberately invalid cross-org link.
        db.query(Lease).filter(Lease.unit_id == occupied.id).order_by(Lease.id.desc()).first().status = LeaseStatus.TERMINATED
        db.query(Lease).filter(Lease.unit_id == occupied.id).order_by(Lease.id.asc()).first().tenant_id = foreign_tenant.id
        db.commit()
        with pytest.raises(ReportDeliveryError, match="tenant scope"):
            _payload(db, admin, property_id=visible.id)
        monkeypatch.setattr(rent_roll, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_export_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(rent_roll, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "TAB" and item.href == "/dashboard/reporting/rent-roll"
        assert report_router.REPORT_PERMISSIONS[KEY] == "LEASING"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={})
        response = Response()
        preview = report_router.preview_rent_roll(req, response, db=db, current_user=admin)
        assert preview["total"] == 4 and response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Current Contract Rent" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        emailed = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={},
            ), db=db, current_user=admin,
        )
        assert emailed.sent and b"Recorded Lease Association" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_rent_roll(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
