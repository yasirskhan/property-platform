"""Expense distribution is dated posted GL activity, not a bill/payment register."""
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
from app.services import expense_distribution as expense
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as reporting_router

KEY = "accounting.expense_distribution"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Expense Org", slug="expense-org")
    other = Organization(name="Foreign Expense Org", slug="foreign-expense-org")
    db.add_all([first, other]); db.flush()
    def user(org, role, label):
        u = User(organization_id=org.id, role=role, first_name=label,
                 last_name="Distribution", email=f"{label.lower()}@expense.example",
                 hashed_password="x", is_active=True)
        db.add(u); db.flush(); return u
    admin = user(first, UserRole.ADMIN, "Admin")
    owner = user(first, UserRole.OWNER, "Owner")
    foreign = user(other, UserRole.ADMIN, "Foreign")
    manager = user(first, UserRole.MANAGER, "Manager")

    def account(org, num, kind="EXPENSE", **opts):
        gl = GLAccount(organization_id=org.id, gl_number=num,
                       name=f"Expense {num}", account_type=kind, **opts)
        db.add(gl); db.flush(); return gl
    repairs = account(first, "=6200")
    utilities = account(first, "6300", is_active=False)
    no_activity = account(first, "6400")
    income = account(first, "4100", "INCOME")
    foreign_expense = account(other, "9999")
    def tx(org, when, gl, debit, credit):
        t = GLTransaction(organization_id=org.id, transaction_date=when,
                          transaction_type="JOURNAL_ENTRY")
        db.add(t); db.flush()
        db.add(GLEntry(organization_id=org.id, transaction_id=t.id,
                       gl_account_id=gl.id, debit=Decimal(debit), credit=Decimal(credit)))
        db.flush()
    tx(first, date(2026, 8, 31), repairs, "900", "0")
    tx(first, date(2026, 9, 1), repairs, "100", "0")
    tx(first, date(2026, 9, 2), repairs, "0", "20")
    tx(first, date(2026, 9, 3), utilities, "0", "10")
    tx(first, date(2026, 9, 4), income, "7000", "0")
    tx(other, date(2026, 9, 1), foreign_expense, "5555", "0")
    db.commit()
    return admin, owner, foreign, manager, repairs, utilities, no_activity


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, current_user=user,
        report_key=KEY, parameters=params,
    )


def test_dated_expense_net_negative_reversals_zero_and_csv_privacy(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, foreign, manager, repairs, utilities, none = _seed(db)
        monkeypatch.setattr(expense, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        report = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        assert len(report.rows) == 3
        rows = {str(row[0]): row for row in report.rows}
        assert rows["=6200"][2:] == (
            Decimal("100"), Decimal("20"), Decimal("80"), Decimal("114.29"),
        )
        assert rows["6300"][2:] == (
            Decimal("0"), Decimal("10"), Decimal("-10"), Decimal("-14.29"),
        )
        assert rows["TOTAL"][2:] == (
            Decimal("100"), Decimal("30"), Decimal("70"), Decimal("100.00"),
        )
        csv_text = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=6200" in csv_text
        for secret in ("Expense 9999", "5555", "7000", "900"):
            assert secret not in csv_text
        assert db.query(GLEntry).count() == before

        zeros = _report(db, admin, date_from="2026-09-01",
                        date_to="2026-09-30", include_zero="true")
        assert any(row[0] == "6400" and row[4] == 0 for row in zeros.rows)
        no_period = _report(db, admin, date_from="2026-10-01", date_to="2026-10-31")
        assert no_period.rows[-1][-1] == "N/A"
        assert no_period.rows[-1][4] == Decimal("0")
    finally:
        db.close(); engine.dispose()


def test_role_org_basis_and_invalid_parameter_rejection(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, foreign, manager, *_ = _seed(db)
        monkeypatch.setattr(expense, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor, date_from="2026-09-01", date_to="2026-09-30")
        for params in (
            {}, {"date_from": "2026-09-01"}, {"date_to": "2026-09-30"},
            {"date_from": "bad", "date_to": "2026-09-30"},
            {"date_from": "2026-10-01", "date_to": "2026-09-30"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30",
             "sql": "SELECT * FROM users"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30",
             "include_zero": "not-a-boolean"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        other = _report(db, foreign, date_from="2026-09-01", date_to="2026-09-30")
        assert other.rows[-1][4] == Decimal("5555")
        assert "Expense =6200" not in str(other)
        monkeypatch.setattr(expense, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        monkeypatch.setattr(expense, "permission_allows_user", lambda *a, **k: True)
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_gate_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(expense, "permission_allows_user", lambda *a, **k: True)
        item = next(r for r in REPORT_CATALOG if r.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/expense-distribution"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={
            "date_from": "2026-09-01", "date_to": "2026-09-30",
        })
        response = Response()
        preview = reporting_router.preview_expense_distribution(
            req, response, db=db, current_user=admin,
        )
        assert preview["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        exported = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Net Posted Expense" in exported.body
        assert b"5555" not in exported.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kwargs: sent.update(kwargs))
        outcome = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="accountant@example.com", parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert outcome.sent and b"5555" not in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_expense_distribution(
                req, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
