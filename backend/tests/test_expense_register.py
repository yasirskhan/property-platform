"""Expense Register is actual dated posted accrual EXPENSE GL entry detail."""
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
from app.services import expense_register as register
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as router

KEY = "transaction.expense_register"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Expense Register Org", slug="expense-register-org")
    other = Organization(name="Foreign Expense Register", slug="foreign-expense-register")
    db.add_all([first, other]); db.flush()
    def person(org, role, name):
        p = User(organization_id=org.id, role=role, first_name=name,
                 last_name="Register", email=f"{name.lower()}@expense-register.example",
                 hashed_password="x", is_active=True)
        db.add(p); db.flush(); return p
    admin = person(first, UserRole.ADMIN, "LocalAdmin")
    manager = person(first, UserRole.MANAGER, "LocalManager")
    foreign = person(other, UserRole.ADMIN, "ForeignAdmin")
    def gl(org, num, kind="EXPENSE", active=True):
        a = GLAccount(organization_id=org.id, gl_number=num,
                      name=f"=Expense {num}" if org==first else "Foreign Expense",
                      account_type=kind, is_active=active)
        db.add(a); db.flush(); return a
    repairs = gl(first, "6200")
    archived = gl(first, "6300", active=False)
    income = gl(first, "4100", "INCOME")
    foreign_expense = gl(other, "6200")
    def entry(org, when, account, debit, credit, reference):
        txn = GLTransaction(organization_id=org.id, transaction_date=when,
                            transaction_type="JOURNAL_ENTRY",
                            reference_number=reference)
        db.add(txn); db.flush()
        item = GLEntry(organization_id=org.id, transaction_id=txn.id,
                       gl_account_id=account.id, description="=Recorded note",
                       debit=Decimal(debit), credit=Decimal(credit))
        db.add(item); db.flush()
        return item
    entry(first, date(2026, 9, 1), repairs, "80", "0", "=J-1")
    entry(first, date(2026, 9, 2), repairs, "0", "20", "REV-1")
    entry(first, date(2026, 9, 3), archived, "0", "10", "REV-2")
    entry(first, date(2026, 9, 2), income, "500", "0", "IN-1")
    entry(first, date(2026, 8, 31), repairs, "999", "0", "OLD")
    entry(other, date(2026, 9, 1), foreign_expense, "5555", "0", "FOREIGN")
    db.commit()
    return admin, manager, foreign, repairs, archived, foreign_expense


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=params,
    )


def test_posted_entry_sign_reversal_archive_csv_scope_and_no_gl_writes(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, repairs, archived, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        before = db.query(GLEntry).count()
        payload = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        assert len(payload.rows) == 4
        assert [row[-1] for row in payload.rows[:3]] == [
            Decimal("80"), Decimal("-20"), Decimal("-10"),
        ]
        assert payload.rows[-1][8:] == (
            Decimal("80"), Decimal("30"), Decimal("50"),
        )
        assert [row[5] for row in payload.rows[:3]] == ["6200", "6200", "6300"]
        only_repairs = _report(db, admin, date_from="2026-09-01",
                               date_to="2026-09-30", account_id=repairs.id)
        assert len(only_repairs.rows) == 3
        assert "cash-basis" in payload.title.lower()
        csv = report_csv_bytes(payload).decode("utf-8-sig")
        assert "'=Recorded note" in csv and "'=J-1" in csv
        assert "'=Expense 6200" in csv
        assert "5555" not in csv and "999" not in csv
        assert db.query(GLEntry).count() == before
    finally:
        db.close(); engine.dispose()


def test_dates_roles_org_and_cash_basis_refused(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, repairs, archived, foreign_expense = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        for params in ({}, {"date_from": "2026-09-01"},
                       {"date_from": "2026-10-01", "date_to": "2026-09-01"},
                       {"date_from": "bad", "date_to": "2026-09-01"},
                       {"date_from": "2026-09-01", "date_to": "2026-09-30",
                        "account_id": foreign_expense.id},
                       {"date_from": "2026-09-01", "date_to": "2026-09-30",
                        "sql": "SELECT * FROM tax_profiles"}):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, manager, date_from="2026-09-01", date_to="2026-09-30")
        assert _report(db, foreign, date_from="2026-09-01",
                       date_to="2026-09-30").rows[-1][-1] == Decimal("5555")
        monkeypatch.setattr(register, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_email_csv_gate_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.href == "/dashboard/reporting/expense-register"
        assert item.presentation == "BUTTON"
        assert router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)],
        )
        req = SimpleNamespace(query_params={"date_from": "2026-09-01", "date_to": "2026-09-30"})
        response = Response()
        result = router.preview_expense_register(req, response, db=db, current_user=admin)
        assert result["total"] == 4 and response.headers["cache-control"] == "no-store"
        exported = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Signed Net Expense" in exported.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        outcome = router.email_report(
            KEY, router.ReportEmailIn(recipient="finance@example.com",
                                      parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert outcome.sent and b"5555" not in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_expense_register(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(
            router, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL",
        )
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
