"""Posted balance sheet presents real account equation or refuses bad books."""
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
from app.models.accounting_settings import AccountingSettings
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.services import account_totals
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "accounting.balance_sheet"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Balance One", slug="balance-sheet-one")
    foreign_org = Organization(name="Balance Other", slug="balance-sheet-two")
    db.add_all([org, foreign_org]); db.flush()
    def user(o, role, name):
        x = User(organization_id=o.id, role=role, first_name=name,
                 last_name="Reader", email=f"{name.lower()}@balance-sheet.example",
                 hashed_password="x", is_active=True)
        db.add(x); db.flush(); return x
    admin = user(org, UserRole.ADMIN, "Admin")
    owner = user(org, UserRole.OWNER, "Owner")
    manager = user(org, UserRole.MANAGER, "Manager")
    foreign = user(foreign_org, UserRole.ADMIN, "Foreign")
    def account(o, number, name, kind, *, active=True):
        acc = GLAccount(organization_id=o.id, gl_number=number,
                        name=name, account_type=kind, is_active=active)
        db.add(acc); db.flush(); return acc
    cash = account(org, "1000", "=Cash", "ASSET")
    liability = account(org, "2000", "Payable", "LIABILITY")
    equity = account(org, "3000", "Capital", "EQUITY")
    income = account(org, "4000", "Income", "INCOME", active=False)
    expense = account(org, "5000", "Expense", "EXPENSE")
    foreign_cash = account(foreign_org, "9999", "Foreign Secret", "ASSET")
    def posting(o, when, debit, credit):
        tx = GLTransaction(organization_id=o.id, transaction_date=when,
                           transaction_type="JOURNAL_ENTRY")
        db.add(tx); db.flush()
        for a, amount in debit:
            db.add(GLEntry(organization_id=o.id, transaction_id=tx.id,
                           gl_account_id=a.id, debit=Decimal(amount), credit=0))
        for a, amount in credit:
            db.add(GLEntry(organization_id=o.id, transaction_id=tx.id,
                           gl_account_id=a.id, debit=0, credit=Decimal(amount)))
        db.flush()
    # Assets 100 = liability 60 + unclosed earnings 40.
    posting(org, date(2026, 8, 1), [(cash, "100.00")],
            [(liability, "60.00"), (income, "40.00")])
    # Valid reversal-like correction: assets 90, earnings 30.
    posting(org, date(2026, 9, 1), [(income, "10.00")], [(cash, "10.00")])
    posting(foreign_org, date(2026, 9, 1), [(foreign_cash, "999.00")],
            [(foreign_cash, "999.00")])
    db.commit()
    return admin, owner, manager, foreign, cash, liability, equity, income, expense


def _payload(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, report_key=KEY,
        current_user=user, parameters=params,
    )


def _row(report, label):
    return next(row for row in report.rows if row[0] == label)


def test_balanced_posted_account_equation_and_reversal(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, cash, liability, equity, income, expense = _seed(db)
        monkeypatch.setattr(account_totals, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        result = _payload(db, admin, as_of="2026-09-01")
        assert _row(result, "TOTAL ASSETS")[-1] == Decimal("90.00")
        assert _row(result, "TOTAL LIABILITIES")[-1] == Decimal("60.00")
        assert _row(result, "UNCLOSED POSTED EARNINGS")[-1] == Decimal("30.00")
        assert _row(result, "TOTAL LIABILITIES + EQUITY + EARNINGS")[-1] == Decimal("90.00")
        assert _row(result, "BALANCE CHECK")[-1] == 0
        assert _row(_payload(db, admin, as_of="2026-08-01"), "TOTAL ASSETS")[-1] == Decimal("100.00")
        csv = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=Cash" in csv and "Foreign Secret" not in csv
        assert db.query(GLEntry).count() == before
    finally:
        db.close(); engine.dispose()


def test_unbalanced_books_and_cash_basis_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, cash, liability, equity, income, expense = _seed(db)
        monkeypatch.setattr(account_totals, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor, as_of="2026-09-01")
        assert "Foreign Secret" not in report_csv_bytes(
            _payload(db, admin, as_of="2026-09-01")).decode("utf-8-sig")
        for params in ({}, {"as_of": "bad"}, {"as_of": "2026-09-01", "sql": "x"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        tx = db.query(GLTransaction).filter(GLTransaction.organization_id == admin.organization_id).first()
        db.add(GLEntry(organization_id=admin.organization_id,
                       transaction_id=tx.id, gl_account_id=cash.id,
                       debit=Decimal("1.00"), credit=0))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="reconcile"):
            _payload(db, admin, as_of="2026-09-01")
        settings = AccountingSettings(organization_id=admin.organization_id,
                                      accounting_basis="CASH")
        db.add(settings); db.commit()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _payload(db, admin, as_of="2026-09-01")
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(account_totals, "permission_allows_user", lambda *a, **k: True)
        entry = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert entry.presentation == "TAB"
        assert entry.href == "/dashboard/reporting/balance-sheet"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"as_of": "2026-09-01"})
        response = Response()
        data = report_router.preview_balance_sheet(req, response, db=db, current_user=admin)
        assert _row(SimpleNamespace(rows=data["rows"]), "TOTAL ASSETS")[-1] == Decimal("90.00")
        assert response.headers["cache-control"] == "no-store"
        assert b"UNCLOSED POSTED EARNINGS" in report_router.export_report_csv(
            KEY, req, db=db, current_user=admin).body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={"as_of": "2026-09-01"}),
            db=db, current_user=admin,
        )
        assert result.sent and b"balance-sheet" in sent["attachments"][0][0].encode()
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_balance_sheet(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
