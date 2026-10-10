"""Income statement reports posted dated revenue less expenses, without GL mutation."""
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
from app.services import income_statement as income
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as reporting_router

KEY = "accounting.income_statement"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Income Org", slug="income-org")
    outsider = Organization(name="Foreign Income Org", slug="foreign-income-org")
    db.add_all([org, outsider]); db.flush()
    def user(company, role, label):
        person = User(organization_id=company.id, role=role,
                      first_name=label, last_name="Income",
                      email=f"{label.lower()}@income.example",
                      hashed_password="x", is_active=True)
        db.add(person); db.flush(); return person
    admin = user(org, UserRole.ADMIN, "Admin")
    owner = user(org, UserRole.OWNER, "Owner")
    manager = user(org, UserRole.MANAGER, "Manager")
    foreign = user(outsider, UserRole.ADMIN, "Foreign")
    def account(company, number, kind, **options):
        row = GLAccount(organization_id=company.id, gl_number=number,
                        name=f"GL {number}", account_type=kind, **options)
        db.add(row); db.flush(); return row
    rent = account(org, "=4100", "INCOME")
    other_income = account(org, "4200", "INCOME", is_active=False)
    repairs = account(org, "6200", "EXPENSE")
    utilities = account(org, "6300", "EXPENSE", is_active=False)
    idle = account(org, "6400", "EXPENSE")
    asset = account(org, "1100", "ASSET")
    foreign_income = account(outsider, "9999", "INCOME")
    def entry(company, day, acct, debit, credit):
        transaction = GLTransaction(organization_id=company.id,
                                    transaction_date=day,
                                    transaction_type="JOURNAL_ENTRY")
        db.add(transaction); db.flush()
        db.add(GLEntry(organization_id=company.id, transaction_id=transaction.id,
                       gl_account_id=acct.id, debit=Decimal(debit),
                       credit=Decimal(credit)))
        db.flush()
    entry(org, date(2026, 8, 31), rent, "0", "9000")
    entry(org, date(2026, 9, 1), rent, "0", "1000")
    entry(org, date(2026, 9, 2), rent, "100", "0")
    entry(org, date(2026, 9, 2), other_income, "200", "0")
    entry(org, date(2026, 9, 3), repairs, "200", "0")
    entry(org, date(2026, 9, 4), repairs, "0", "50")
    entry(org, date(2026, 9, 5), utilities, "0", "30")
    entry(org, date(2026, 9, 6), asset, "99999", "0")
    entry(outsider, date(2026, 9, 1), foreign_income, "0", "88888")
    db.commit()
    return admin, owner, manager, foreign


def _report(db, actor, **parameters):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=parameters,
    )


def test_signed_revenue_expense_reversal_archived_accounts_and_csv(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(income, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        result = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        rows = {str(r[1]): r for r in result.rows if r[1]}
        assert rows["=4100"] == ("INCOME", "=4100", "GL =4100",
                                 Decimal("100"), Decimal("1000"), Decimal("900"))
        assert rows["4200"][-1] == Decimal("-200")
        assert rows["6200"][-1] == Decimal("150")
        assert rows["6300"][-1] == Decimal("-30")
        assert result.rows[-2] == ("TOTAL POSTED EXPENSE", "", "", "", "", Decimal("120"))
        assert result.rows[-1][-1] == Decimal("580")
        assert result.rows[-1][0] == "NET POSTED INCOME LESS EXPENSE"
        text = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=4100" in text
        assert "88888" not in text and "99999" not in text and "9000" not in text
        assert db.query(GLEntry).count() == before
        all_accounts = _report(db, admin, date_from="2026-09-01",
                               date_to="2026-09-30", include_zero="true")
        assert any(r[1] == "6400" and r[-1] == 0 for r in all_accounts.rows)
        empty = _report(db, admin, date_from="2026-10-01", date_to="2026-10-31")
        assert empty.rows[-1][-1] == Decimal("0")
        assert len(empty.rows) == 3
    finally:
        db.close(); engine.dispose()


def test_invalid_period_org_roles_permissions_and_cash_basis(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign = _seed(db)
        monkeypatch.setattr(income, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor, date_from="2026-09-01", date_to="2026-09-30")
        for parameters in (
            {}, {"date_from": "2026-09-01"},
            {"date_to": "2026-09-30"},
            {"date_from": "bad", "date_to": "2026-09-30"},
            {"date_from": "2026-10-01", "date_to": "2026-09-30"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30", "sql": "select *"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30", "include_zero": "garbage"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **parameters)
        other = _report(db, foreign, date_from="2026-09-01", date_to="2026-09-30")
        assert other.rows[-1][-1] == Decimal("88888")
        with pytest.raises(ReportDeliveryError, match="permission"):
            build_report_payload(db, organization_id=foreign.organization_id,
                                 current_user=admin, report_key=KEY,
                                 parameters={"date_from": "2026-09-01", "date_to": "2026-09-30"})
        monkeypatch.setattr(income, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        monkeypatch.setattr(income, "permission_allows_user", lambda *a, **k: True)
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_export_email_and_gate_rechecks(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(income, "permission_allows_user", lambda *a, **k: True)
        item = next(r for r in REPORT_CATALOG if r.key == KEY)
        assert item.presentation == "TAB"
        assert item.href == "/dashboard/reporting/income-statement"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={
            "date_from": "2026-09-01", "date_to": "2026-09-30",
        })
        response = Response()
        preview = reporting_router.preview_income_statement(
            req, response, db=db, current_user=admin,
        )
        assert preview["total"] == 7
        assert response.headers["cache-control"] == "no-store"
        exported = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"NET POSTED INCOME LESS EXPENSE" in exported.body
        assert b"88888" not in exported.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="accountant@example.com", parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert result.sent and b"88888" not in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_income_statement(
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
