"""Aged payables ages today's verified posted Bill open metadata only."""
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
from app.models.accounting_settings import AccountingSettings
from app.models.bill import Bill
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.services import aged_payables as aging
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as reporting_router

KEY = "transaction.aged_payables"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Payables Age One", slug="payables-age-one")
    second = Organization(name="Payables Age Two", slug="payables-age-two")
    db.add_all([first, second]); db.flush()
    def user(org, role, name):
        u = User(organization_id=org.id, role=role, first_name=name,
                 last_name="Aging", email=f"{name}@aging.example",
                 hashed_password="x", is_active=True)
        db.add(u); db.flush(); return u
    admin = user(first, UserRole.ADMIN, "admin")
    owner = user(first, UserRole.OWNER, "owner")
    manager = user(first, UserRole.MANAGER, "manager")
    foreign_admin = user(second, UserRole.ADMIN, "foreign")
    def account(org):
        gl = GLAccount(organization_id=org.id, gl_number="2100",
                       name="Accounts payable", account_type="LIABILITY")
        db.add(gl); db.flush(); return gl
    payable = account(first)
    foreign_payable = account(second)
    today = date.today()
    bills = {}
    def bill(label, org=first, due=None, amount="100", paid="0",
             status="UNPAID", *, reversed=False, active=True, posted=True,
             gl=None, bill_date=None):
        account = gl or (payable if org.id == first.id else foreign_payable)
        transaction = None
        if posted:
            transaction = GLTransaction(
                organization_id=org.id, transaction_date=bill_date or today,
                transaction_type="BILL",
            )
            db.add(transaction); db.flush()
        obj = Bill(
            organization_id=org.id, payee_name="=Invoice Supplier" if label == "1-30" else label,
            bill_number=label, bill_date=bill_date or today, due_date=due,
            payable_gl_account_id=account.id,
            gl_transaction_id=transaction.id if transaction else None,
            amount=Decimal(amount), amount_paid=Decimal(paid),
            status=status, is_reversed=reversed, is_active=active,
        )
        db.add(obj); db.flush()
        bills[label] = obj
        return obj
    for label, days in (("1-30", 30), ("31-60", 31), ("61-90", 61), ("91+", 91)):
        bill(label, due=today - timedelta(days=days))
    bill("60-days", due=today - timedelta(days=60), amount="125", paid="25", status="PARTIAL")
    bill("90-days", due=today - timedelta(days=90), amount="150", paid="50", status="PARTIAL")
    bill("due-today", due=today)
    bill("future-due", due=today + timedelta(days=7))
    bill("no-due", due=None)
    bill("paid", due=today - timedelta(days=999), amount="100", paid="100", status="PAID")
    bill("void", due=today - timedelta(days=1), status="VOID")
    bill("reversed", due=today - timedelta(days=1), reversed=True)
    bill("unposted", due=today - timedelta(days=1), posted=False)
    bill("inactive", due=today - timedelta(days=1), active=False)
    bill("future-bill", due=today + timedelta(days=1), bill_date=today + timedelta(days=1))
    bill("foreign", org=second, due=today - timedelta(days=91), amount="99999")
    db.commit()
    return admin, owner, manager, foreign_admin, bills, payable


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, current_user=user,
        report_key=KEY, parameters=params,
    )


def test_current_unpaid_due_bucket_boundaries_and_csv_privacy(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, bills, _ = _seed(db)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        count = db.query(GLTransaction).count()
        report = _report(db, admin)
        live = {r[1]: r for r in report.rows if isinstance(r[0], int)}
        assert len(live) == 9
        assert live["1-30"][-1] == "1-30 DAYS" and live["1-30"][-2] == 30
        assert live["31-60"][-1] == "31-60 DAYS"
        assert live["60-days"][-1] == "31-60 DAYS"
        assert live["61-90"][-1] == "61-90 DAYS"
        assert live["90-days"][-1] == "61-90 DAYS"
        assert live["91+"][-1] == "91+ DAYS"
        assert live["due-today"][-1] == "DUE TODAY"
        assert live["future-due"][-1] == "NOT YET DUE"
        assert live["no-due"][-1] == "DUE DATE NOT RECORDED"
        assert live["no-due"][-2] == ""
        assert live["60-days"][6] == Decimal("100")
        assert live["90-days"][6] == Decimal("100")
        assert report.rows[-1][6] == Decimal("900")
        totals = {r[1]: r[6] for r in report.rows if r[0] == "BUCKET"}
        assert totals["1-30 DAYS"] == Decimal("100")
        assert totals["31-60 DAYS"] == Decimal("200")
        assert totals["61-90 DAYS"] == Decimal("200")
        assert totals["91+ DAYS"] == Decimal("100")
        assert totals["NOT YET DUE"] == Decimal("100")
        assert totals["DUE TODAY"] == Decimal("100")
        assert totals["DUE DATE NOT RECORDED"] == Decimal("100")
        csv = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Invoice Supplier" in csv
        for forbidden in ("99999", "foreign", "unposted", "future-bill", "reversed"):
            assert forbidden not in csv
        assert db.query(GLTransaction).count() == count
        assert "not a historic" in report.title.lower() or "not a historic" in str(report.title).lower()
    finally:
        db.close(); engine.dispose()


def test_bad_current_metadata_roles_org_and_historical_snapshot_denied(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, bills, payable = _seed(db)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor)
        assert _report(db, foreign).rows[-1][6] == Decimal("99999")
        for params in (
            {"sql": "select * from payee"},
            {"as_of": "not-a-date"},
            {"as_of": (date.today() - timedelta(days=1)).isoformat()},
            {"as_of": (date.today() + timedelta(days=1)).isoformat()},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        monkeypatch.setattr(aging, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.PAYABLES")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        for bad_amount, bad_paid in (("-1", "0"), ("100", "-1"), ("100", "101")):
            b = bills["1-30"]
            b.amount, b.amount_paid = Decimal(bad_amount), Decimal(bad_paid)
            db.flush()
            with pytest.raises(ReportDeliveryError, match="Invalid"):
                _report(db, admin)
        b.amount, b.amount_paid = Decimal("100"), Decimal("0")
        b.payable_gl_account_id = bills["foreign"].payable_gl_account_id
        db.flush()
        with pytest.raises(ReportDeliveryError, match="mapping"):
            _report(db, admin)
        b.payable_gl_account_id = payable.id
        db.flush()
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.flush()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _report(db, admin)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_catalog_preview_email_csv_export_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/aged-payables"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.PAYABLES"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={})
        response = Response()
        before = db.query(GLTransaction).count()
        preview = reporting_router.preview_aged_payables(req, response, db=db, current_user=admin)
        assert preview["total"] == 17
        assert response.headers["cache-control"] == "no-store"
        csv = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Current Recorded Unpaid" in csv.body
        assert b"99999" not in csv.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="accountant@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert result.sent and b"99999" not in sent["attachments"][0][1]
        assert db.query(GLTransaction).count() == before
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_aged_payables(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
