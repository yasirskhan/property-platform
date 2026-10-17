"""Lease contract ending detail and month summary, guarded against tenant leaks."""
from __future__ import annotations

from datetime import date
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
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.services import lease_expiration_report
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)
from app.routers import reporting as report_router

DETAIL = "property.lease_expiration_detail"
SUMMARY = "property.lease_expiration_summary"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Lease Exp One", slug="lease-exp-one")
    other = Organization(name="Lease Exp Other", slug="lease-exp-other")
    db.add_all((org, other)); db.flush()
    def user(o, role, name):
        u = User(organization_id=o.id, role=role, first_name=name,
                 last_name="Lease", email=f"{name.lower()}@lease-exp.example",
                 hashed_password="x", is_active=True)
        db.add(u); db.flush()
        return u
    admin = user(org, UserRole.ADMIN, "Admin")
    manager = user(org, UserRole.MANAGER, "Manager")
    tenant = user(org, UserRole.TENANT, "Tenant")
    foreign_admin = user(other, UserRole.ADMIN, "Foreign")
    foreign_tenant = user(other, UserRole.TENANT, "Outsider")
    def prop(o, label):
        p = Property(organization_id=o.id, name=label,
                     address_line1="1 Legal Lane", city="Cleveland", state="OH",
                     zip_code="44113", is_active=True)
        db.add(p); db.flush()
        return p
    first = prop(org, "=First")
    hidden = prop(org, "Unassigned")
    outside = prop(other, "Foreign")
    db.add(PropertyAssignment(property_id=first.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    def lease(p, who, ending, status, number="A", rent="1000"):
        u = Unit(property_id=p.id, unit_number=number, monthly_rent=rent,
                 is_active=True)
        db.add(u); db.flush()
        l = Lease(unit_id=u.id, tenant_id=who.id, start_date=date(2025, 1, 1),
                  end_date=ending, monthly_rent=Decimal(rent),
                  security_deposit=0, status=status)
        db.add(l); db.flush()
        return l
    a = lease(first, tenant, date(2026, 6, 14), LeaseStatus.ACTIVE, number="=A", rent="1200")
    b = lease(first, tenant, date(2026, 6, 30), LeaseStatus.EXPIRED, number="B", rent="900")
    lease(first, tenant, date(2026, 7, 1), LeaseStatus.TERMINATED, number="C")
    lease(first, tenant, date(2026, 6, 30), LeaseStatus.DRAFT, number="D")
    lease(hidden, tenant, date(2026, 6, 20), LeaseStatus.ACTIVE, number="E", rent="2200")
    lease(outside, foreign_tenant, date(2026, 6, 20), LeaseStatus.ACTIVE, number="F", rent="3300")
    db.commit()
    return admin, manager, tenant, foreign_admin, first, hidden, outside, a, b


def _payload(db, actor, key=DETAIL, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=key,
        parameters={"date_from": "2026-06-01", "date_to": "2026-06-30", **params},
        current_user=actor,
    )


def test_contract_endings_and_month_summary_not_movement_or_gl(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, hidden, _, a, b = _seed(db)
        monkeypatch.setattr(lease_expiration_report, "permission_allows_user", lambda *args, **kw: True)
        count = db.query(GLTransaction).count()
        detail = _payload(db, admin)
        assert len(detail.rows) == 3
        ids = {row[4] for row in detail.rows}
        assert a.id in ids and b.id in ids
        assert detail.rows[0][0] == date(2026, 6, 14)
        assert next(row for row in detail.rows if row[4] == b.id)[6] == "EXPIRED"
        assert "'=First" in report_csv_bytes(detail).decode("utf-8-sig")
        assert "'=A" in report_csv_bytes(detail).decode("utf-8-sig")
        summary = _payload(db, admin, key=SUMMARY)
        assert len(summary.rows) == 2
        first_group = next(x for x in summary.rows if x[4] == first.id)
        assert first_group[0] == "2026-06" and first_group[2] == 2
        assert first_group[3] == Decimal("2100.00")
        assert next(x for x in summary.rows if x[4] == hidden.id)[3] == Decimal("2200.00")
        assert db.query(GLTransaction).count() == count
    finally:
        db.close(); engine.dispose()


def test_manager_scope_inactive_and_foreign_tenant_protection(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, hidden, outside, a, b = _seed(db)
        monkeypatch.setattr(lease_expiration_report, "permission_allows_user", lambda *args, **kw: True)
        assert len(_payload(db, manager).rows) == 2
        for p in (hidden, outside):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=p.id)
        for actor in (tenant, foreign_admin):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, property_id=first.id)
        # Broken cross-org tenant linkage must not expose another tenant.
        unit = db.query(Unit).filter(Unit.property_id == first.id).first()
        foreign_person = db.query(User).filter(User.role == UserRole.TENANT,
                                               User.organization_id == foreign_admin.organization_id).one()
        db.add(Lease(unit_id=unit.id, tenant_id=foreign_person.id,
                     start_date=date(2025, 1, 1), end_date=date(2026, 6, 18),
                     monthly_rent=9999, security_deposit=0, status=LeaseStatus.ACTIVE))
        db.commit()
        assert len(_payload(db, admin, property_id=first.id).rows) == 2
        tenant.is_active = False
        db.commit()
        assert len(_payload(db, admin).rows) == 0
    finally:
        db.close(); engine.dispose()


def test_bad_ranges_and_authorization_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, _, _, first, *_ = _seed(db)
        monkeypatch.setattr(lease_expiration_report, "permission_allows_user", lambda *args, **kw: True)
        for bad in (
            {"date_from": ""}, {"date_to": ""},
            {"date_from": "2026-13-01"},
            {"date_from": "2027-01-01", "date_to": "2026-01-01"},
            {"date_from": "2000-01-01", "date_to": "2026-01-01"},
            {"property_id": -1}, {"sql": "SELECT * FROM users"},
        ):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **bad)
        monkeypatch.setattr(lease_expiration_report, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(lease_expiration_report, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.ALL")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_export_email_and_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, *_ = _seed(db)
        monkeypatch.setattr(lease_expiration_report, "permission_allows_user", lambda *args, **kw: True)
        for key in (DETAIL, SUMMARY):
            row = next(item for item in REPORT_CATALOG if item.key == key)
            assert row.tier == "STANDARD" and row.href is not None
            if key == SUMMARY:
                assert row.href == "/dashboard/reporting/lease-expirations/summary"
            assert report_router.REPORT_PERMISSIONS[key] == "LEASING"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *args, **kw: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *args, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={
            "report_key": DETAIL, "date_from": "2026-06-01",
            "date_to": "2026-06-30", "property_id": str(first.id),
        })
        response = Response()
        result = report_router.preview_lease_expirations(req, response, db=db, current_user=admin)
        assert result["total"] == 2 and response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(
            DETAIL, SimpleNamespace(query_params={
                "date_from": "2026-06-01", "date_to": "2026-06-30",
                "property_id": str(first.id),
            }), db=db, current_user=admin,
        )
        assert b"Scheduled Contract End" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        result = report_router.email_report(
            SUMMARY, report_router.ReportEmailIn(
                recipient="staff@example.com",
                parameters={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"Scheduled End Month" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *args, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_lease_expirations(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(
                SUMMARY,
                SimpleNamespace(query_params={"date_from": "2026-06-01",
                                              "date_to": "2026-06-30"}),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            report_router.preview_lease_expirations(
                SimpleNamespace(query_params={"report_key": "property.foo"}),
                Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()
