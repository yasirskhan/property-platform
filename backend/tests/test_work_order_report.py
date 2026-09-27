"""Work-order reporting obeys tenant privacy and live property visibility."""
from __future__ import annotations

from datetime import datetime
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
from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderCategory, WorkOrderPriority
from app.services import work_order_report
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "maintenance.work_order"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Work Order One", slug="work-order-one")
    other = Organization(name="Work Order Other", slug="work-order-other")
    db.add_all([org, other]); db.flush()
    def person(o, role, name):
        row = User(organization_id=o.id, role=role, first_name=name,
                   last_name="Worker", hashed_password="x",
                   email=f"{name.lower()}@work-order-report.example", is_active=True)
        db.add(row); db.flush(); return row
    admin = person(org, UserRole.ADMIN, "Admin")
    owner = person(org, UserRole.OWNER, "Owner")
    manager = person(org, UserRole.MANAGER, "Manager")
    tenant = person(org, UserRole.TENANT, "Tenant")
    foreign = person(other, UserRole.ADMIN, "Foreign")
    foreign_tenant = person(other, UserRole.TENANT, "ForeignTenant")
    def location(o, name):
        prop = Property(organization_id=o.id, name=name,
                        address_line1="100 Address", city="Cleveland",
                        state="OH", zip_code="44113", is_active=True)
        db.add(prop); db.flush()
        unit = Unit(property_id=prop.id, unit_number="A1",
                    bedrooms=1, bathrooms=1, monthly_rent=100)
        db.add(unit); db.flush()
        return prop, unit
    p1, u1 = location(org, "Assigned")
    p2, u2 = location(org, "Unassigned")
    p3, u3 = location(other, "Foreign")
    db.add(PropertyAssignment(property_id=p1.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    db.flush()
    def order(prop, unit, person_, name, status=WorkOrderStatus.SUBMITTED):
        row = WorkOrder(
            property_id=prop.id, unit_id=unit.id, tenant_id=person_.id,
            title=name, description="Sensitive tenant issue",
            entry_notes="Access code 1234", photo_urls="private-photo.jpg",
            status=status, category=WorkOrderCategory.PLUMBING,
            priority=WorkOrderPriority.HIGH,
            created_at=datetime(2026, 9, 20, 13, 0),
            total_cost=Decimal("65.00"),
        )
        db.add(row); db.flush(); return row
    first = order(p1, u1, tenant, "=Leaky faucet")
    second = order(p2, u2, tenant, "Second", WorkOrderStatus.CLOSED)
    third = order(p3, u3, foreign_tenant, "Private")
    db.commit()
    return admin, owner, manager, tenant, foreign, p1, p2, p3, first, second, third


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        parameters=params, current_user=actor,
    )


def test_recorded_work_orders_no_private_entry_notes_or_cross_org(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, tenant, foreign, p1, p2, p3, first, second, third = _seed(db)
        monkeypatch.setattr(work_order_report, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        rows = _payload(db, admin).rows
        assert {row[1] for row in rows} == {first.id, second.id}
        assert [row[1] for row in _payload(db, manager).rows] == [first.id]
        assert len(_payload(db, owner).rows) == 2
        assert len(_payload(db, foreign).rows) == 1
        assert rows[0][-1] == Decimal("65.00")
        content = report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert "'=Leaky faucet" in content
        for private in ("Access code 1234", "Sensitive tenant issue", "private-photo.jpg",
                        "ForeignTenant", "Private"):
            assert private not in content
        assert db.query(GLTransaction).count() == before
    finally:
        db.close(); engine.dispose()


def test_manager_property_scope_and_bad_filters(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, tenant, foreign, p1, p2, p3, first, second, third = _seed(db)
        monkeypatch.setattr(work_order_report, "permission_allows_user", lambda *a, **k: True)
        assert len(_payload(db, manager, property_id=p1.id).rows) == 1
        for prop in (p2, p3):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=prop.id)
        for params in (
            {"sql": "SELECT * FROM tax_profiles"},
            {"status": "not-real"},
            {"date_from": "2026-09-21", "date_to": "2026-09-20"},
            {"property_id": "-1"},
        ):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        assert len(_payload(db, admin, status="submitted").rows) == 1
        assert _payload(db, admin, date_from="2026-09-21").rows == ()
    finally:
        db.close(); engine.dispose()


def test_roles_permission_revocation_and_no_gl_mutations(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, tenant, *_ = _seed(db)
        monkeypatch.setattr(work_order_report, "permission_allows_user", lambda *a, **k: True)
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, tenant)
        monkeypatch.setattr(
            work_order_report, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "MAINTENANCE.WORK_ORDERS",
        )
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(work_order_report, "permission_allows_user", lambda *a, **k: True)
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_csv_email_preview_and_release_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(work_order_report, "permission_allows_user", lambda *a, **k: True)
        entry = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert entry.presentation == "BUTTON"
        assert entry.href == "/dashboard/reporting/work-orders"
        assert report_router.REPORT_PERMISSIONS[KEY] == "MAINTENANCE.WORK_ORDERS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={})
        response = Response()
        result = report_router.preview_work_order_report(req, response, db=db, current_user=admin)
        assert result["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        csv = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Work Order ID" in csv.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert result.sent and b"Leaky faucet" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_work_order_report(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
