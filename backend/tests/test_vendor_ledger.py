"""Vendor financial report is linked-bill only, bounded and read-only."""
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
from app.models.bill import Bill
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.services import vendor_ledger
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "vendor.ledger"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Vendor Ledger One", slug="vendor-ledger-one")
    other = Organization(name="Vendor Ledger Two", slug="vendor-ledger-two")
    db.add_all([first, other]); db.flush()
    def user(org, role, first_name):
        person = User(organization_id=org.id, role=role, first_name=first_name,
                      last_name="=Payee", email=f"{first_name.lower()}@vendor-ledger.example",
                      hashed_password="x", is_active=True)
        db.add(person); db.flush(); return person
    admin = user(first, UserRole.ADMIN, "Admin")
    owner = user(first, UserRole.OWNER, "Owner")
    manager = user(first, UserRole.MANAGER, "Manager")
    vendor = user(first, UserRole.VENDOR, "=Vendor")
    another = user(first, UserRole.VENDOR, "Another")
    foreign = user(other, UserRole.VENDOR, "Foreign")
    foreign_admin = user(other, UserRole.ADMIN, "OtherAdmin")
    def bill(org, person, number, amount, paid, *, active=True, status="PARTIAL", reversed=False):
        row = Bill(
            organization_id=org.id, payee_name=person.first_name if person else "Unlinked",
            payee_user_id=person.id if person else None,
            bill_number=number, bill_date=date(2026, 9, 20),
            payable_gl_account_id=1, amount=Decimal(amount),
            amount_paid=Decimal(paid), status=status,
            is_active=active, is_reversed=reversed,
        )
        db.add(row); db.flush(); return row
    linked = bill(first, vendor, "V-001", "175.00", "75.00")
    other_linked = bill(first, another, "V-002", "90.00", "90.00", status="PAID")
    bill(first, None, "UNLINKED", "99.00", "0.00")
    bill(first, owner, "OWNER", "50.00", "0.00")
    bill(first, foreign, "WRONG-ORG", "200.00", "0.00")
    bill(other, foreign, "OTHER-ORG", "300.00", "0.00")
    bill(first, vendor, "VOID", "100.00", "0.00", status="VOID")
    bill(first, vendor, "REVERSED", "40.00", "0.00", reversed=True)
    bill(first, vendor, "INACTIVE", "33.00", "0.00", active=False)
    db.commit()
    return admin, owner, manager, vendor, another, foreign, foreign_admin, linked, other_linked


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        current_user=actor, parameters=params,
    )


def test_linked_vendor_bills_only_amounts_and_csv_escape(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, vendor, another, foreign, foreign_admin, linked, other_linked = _seed(db)
        monkeypatch.setattr(vendor_ledger, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        result = _payload(db, admin)
        assert {row[3] for row in result.rows} == {linked.id, other_linked.id}
        assert result.rows[0][6:] == (Decimal("175.00"), Decimal("75.00"), Decimal("100.00"))
        assert result.rows[1][6:] == (Decimal("90.00"), Decimal("90.00"), Decimal("0.00"))
        csv = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=Vendor =Payee" in csv
        assert "Foreign" not in csv and "UNLINKED" not in csv and "REVERSED" not in csv
        assert len(result.headers) == 9
        assert db.query(GLTransaction).count() == before
        assert [row[3] for row in _payload(db, admin, vendor_id=str(vendor.id)).rows] == [linked.id]
        assert _payload(db, admin, date_from="2026-09-21").rows == ()
    finally:
        db.close(); engine.dispose()


def test_role_permission_and_org_scope_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, vendor, another, foreign, foreign_admin, *_ = _seed(db)
        monkeypatch.setattr(vendor_ledger, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager, vendor, foreign):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor)
        assert len(_payload(db, foreign_admin).rows) == 1
        for value in (foreign.id, "-1", "abc"):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, vendor_id=value)
        for params in ({"sql": "SELECT * FROM tax_profiles"},
                       {"date_from": "2026-10-01", "date_to": "2026-09-01"},
                       {"date_to": "bad-date"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        monkeypatch.setattr(
            vendor_ledger, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.PAYABLES",
        )
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(vendor_ledger, "permission_allows_user", lambda *a, **k: True)
        admin.is_active = False; db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_corrupt_payment_metadata_fails_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, _, _, _, linked, _ = _seed(db)
        monkeypatch.setattr(vendor_ledger, "permission_allows_user", lambda *a, **k: True)
        linked.amount_paid = Decimal("999.00"); db.commit()
        with pytest.raises(ReportDeliveryError, match="Invalid"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(vendor_ledger, "permission_allows_user", lambda *a, **k: True)
        entry = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert entry.presentation == "TAB"
        assert entry.href == "/dashboard/reporting/vendor-ledger"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.PAYABLES"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={})
        response = Response()
        report = report_router.preview_vendor_ledger(req, response, db=db, current_user=admin)
        assert report["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        assert b"Recorded Unpaid" in report_router.export_report_csv(
            KEY, req, db=db, current_user=admin).body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(recipient="staff@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert result.sent and b"V-001" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_vendor_ledger(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
