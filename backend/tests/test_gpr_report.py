"""GPR read-only projection, org/manager scope, journal markers and delivery."""
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
from app.models.gl_entry import GLEntry
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.services import gpr_report, property_budgets
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)
from app.services.report_catalog import REPORT_CATALOG
from app.routers import reporting as report_router

KEY = "property.gross_potential_rent"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="GPR Reporting One", slug="gpr-report-one")
    two = Organization(name="GPR Reporting Two", slug="gpr-report-two")
    db.add_all([one, two])
    db.flush()
    def user(org, role, name):
        item = User(
            organization_id=org.id, role=role, first_name=name,
            last_name="GPR", email=f"{name.lower()}@gpr-report.example",
            hashed_password="x", is_active=True,
        )
        db.add(item); db.flush()
        return item
    admin = user(one, UserRole.ADMIN, "Admin")
    manager = user(one, UserRole.MANAGER, "Manager")
    tenant = user(one, UserRole.TENANT, "Tenant")
    other = user(two, UserRole.ADMIN, "Foreign")
    def prop(org, name):
        p = Property(
            organization_id=org.id, name=name,
            address_line1="1 Recorded Lane", city="Cleveland", state="OH",
            zip_code="44113", is_active=True,
        )
        db.add(p); db.flush()
        return p
    first = prop(one, "=First GPR")
    unassigned = prop(one, "Unassigned GPR")
    foreign = prop(two, "Foreign GPR")
    db.add(PropertyAssignment(property_id=first.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    def unit(prop_, number, market):
        row = Unit(
            property_id=prop_.id, unit_number=number,
            monthly_rent=Decimal(market), is_active=True,
        )
        db.add(row); db.flush()
        return row
    occupied = unit(first, "1", "1500")
    vacant = unit(first, "=2", "1200")
    other_unit = unit(unassigned, "3", "3100")
    foreign_unit = unit(foreign, "4", "4400")
    lease = Lease(unit_id=occupied.id, tenant_id=tenant.id,
                  start_date=date(2026, 1, 1),
                  end_date=date(2026, 12, 31),
                  monthly_rent=Decimal("1400"), security_deposit=0,
                  status=LeaseStatus.ACTIVE)
    db.add(lease)
    db.commit()
    return admin, manager, tenant, other, first, unassigned, foreign, occupied, vacant, other_unit, foreign_unit


def _payload(db, actor, prop, month="2026-06-01", **extra):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        parameters={"property_id": prop.id, "month": month, **extra},
        current_user=actor,
    )


def test_current_projection_vacant_and_no_gl_changes(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, *rest = _seed(db)
        occupied, vacant = rest[2], rest[3]
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(gpr_report, "permission_allows_user", lambda *a, **kw: True)
        before = db.query(GLTransaction).count()
        result = _payload(db, admin, first)
        assert result.title.startswith("Gross potential rent projection")
        assert len(result.rows) == 2
        leased = next(x for x in result.rows if x[-1] == occupied.id)
        vacancy = next(x for x in result.rows if x[-1] == vacant.id)
        assert leased[3:7] == (
            "LEASED", Decimal("1500.00"), Decimal("1400.00"), Decimal("100.00"),
        )
        assert vacancy[3:7] == (
            "VACANT", Decimal("1200.00"), Decimal("0.00"), Decimal("1200.00"),
        )
        assert all(row[8] == "NOT POSTED" for row in result.rows)
        assert db.query(GLTransaction).count() == before
        assert "'=First GPR" in report_csv_bytes(result).decode("utf-8-sig")
        assert "'=2" in report_csv_bytes(result).decode("utf-8-sig")
        assert _payload(db, admin, first, month="2026-06-30").rows == result.rows
        assert db.query(GLEntry).count() == 0
    finally:
        db.close(); engine.dispose()


def test_gpr_post_marker_reversal_and_current_config_not_backdated(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, _, _, occupied, *_ = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(gpr_report, "permission_allows_user", lambda *a, **kw: True)
        original = GLTransaction(
            organization_id=admin.organization_id, transaction_date=date(2026, 6, 1),
            transaction_type="JOURNAL_ENTRY", source_type="gpr",
            source_id=occupied.id, is_reversed=False,
        )
        db.add(original); db.commit()
        first_report = _payload(db, admin, first)
        first_row = next(row for row in first_report.rows if row[-1] == occupied.id)
        assert first_row[8].startswith("POSTED") and first_row[9] == original.id
        original.is_reversed = True
        reversal = GLTransaction(
            organization_id=admin.organization_id, transaction_date=date(2026, 6, 12),
            transaction_type="REVERSAL", reversal_of_id=original.id,
        )
        db.add(reversal); db.commit()
        reversal_row = next(row for row in _payload(db, admin, first).rows if row[-1] == occupied.id)
        assert reversal_row[8].startswith("REVERSED") and reversal_row[10] == reversal.id
        current_lease = db.query(Lease).filter(Lease.unit_id == occupied.id).one()
        current_lease.monthly_rent = Decimal("900")
        db.commit()
        changed_row = next(row for row in _payload(db, admin, first).rows if row[-1] == occupied.id)
        assert changed_row[5] == Decimal("900.00")
        assert changed_row[8].startswith("REVERSED") and changed_row[10] == reversal.id
        assert db.query(GLTransaction).count() == 2
    finally:
        db.close(); engine.dispose()


def test_scope_overlap_and_invalid_month_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, unassigned, foreign, occupied, *_ = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(gpr_report, "permission_allows_user", lambda *a, **kw: True)
        assert len(_payload(db, manager, first).rows) == 2
        for prop in (unassigned, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, prop)
        for actor in (tenant, foreign_admin):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, first)
        for extras in (
            {"sql": "select"}, {"month": "2026-13-01"},
            {"month": ""}, {"month": "2101-01-01"}, {"property_id": 99999},
        ):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, first, **extras)
        db.add(Lease(
            unit_id=occupied.id, tenant_id=tenant.id,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 30),
            monthly_rent=Decimal("1500"), security_deposit=0,
            status=LeaseStatus.ACTIVE,
        ))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="multiple active leases"):
            _payload(db, admin, first)
    finally:
        db.close(); engine.dispose()


def test_preview_csv_email_authorization_gate_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, *_ = _seed(db)
        first = db.query(Property).filter(Property.name == "=First GPR").one()
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(gpr_report, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "TAB" and item.href == "/dashboard/reporting/gross-potential-rent"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={"property_id": str(first.id), "month": "2026-06-01"})
        response = Response()
        preview = report_router.preview_gross_potential_rent(
            req, response, db=db, current_user=admin,
        )
        assert preview["total"] == 2 and response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Current Config Market Rent" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com",
                parameters={"property_id": first.id, "month": "2026-06-01"},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"Journal Marker" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_gross_potential_rent(
                req, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(gpr_report, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin, first)
        monkeypatch.setattr(property_budgets, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.ALL")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin, first)
    finally:
        db.close(); engine.dispose()
