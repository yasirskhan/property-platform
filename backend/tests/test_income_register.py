"""Income Register is actual dated posted accrual INCOME GL entry detail."""
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
from app.services import income_register as register
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as router

KEY = "transaction.income_register"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Income Register Org", slug="income-register-org")
    other = Organization(name="Other Income Register", slug="other-income-register")
    db.add_all([first, other])
    db.flush()

    def person(org, role, name):
        user = User(organization_id=org.id, role=role, first_name=name,
                    last_name="Register", email=f"{name.lower()}@income-register.example",
                    hashed_password="x", is_active=True)
        db.add(user)
        db.flush()
        return user

    admin = person(first, UserRole.ADMIN, "LocalAdmin")
    manager = person(first, UserRole.MANAGER, "LocalManager")
    foreign = person(other, UserRole.ADMIN, "ForeignAdmin")

    def gl(org, number, kind="INCOME", active=True):
        acc = GLAccount(organization_id=org.id, gl_number=number,
                        name=f"=Income {number}" if org == first else "Foreign Income",
                        account_type=kind, is_active=active)
        db.add(acc)
        db.flush()
        return acc

    rents = gl(first, "4100")
    archived = gl(first, "4200", active=False)
    expense = gl(first, "6200", "EXPENSE")
    foreign_income = gl(other, "4100")

    def entry(org, when, account, debit, credit, reference):
        txn = GLTransaction(organization_id=org.id, transaction_date=when,
                            transaction_type="JOURNAL_ENTRY",
                            reference_number=reference)
        db.add(txn)
        db.flush()
        item = GLEntry(organization_id=org.id, transaction_id=txn.id,
                       gl_account_id=account.id, description="=Recorded income",
                       debit=Decimal(debit), credit=Decimal(credit))
        db.add(item)
        db.flush()
        return item

    entry(first, date(2026, 9, 1), rents, "0", "100", "=R-1")
    entry(first, date(2026, 9, 2), rents, "25", "0", "RET-1")
    entry(first, date(2026, 9, 3), archived, "0", "10", "REV-2")
    entry(first, date(2026, 9, 2), expense, "0", "500", "EX-1")
    entry(first, date(2026, 8, 31), rents, "0", "999", "OLD")
    entry(other, date(2026, 9, 1), foreign_income, "0", "5555", "FOREIGN")
    db.commit()
    return admin, manager, foreign, rents, archived, foreign_income


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=params,
    )


def test_posted_income_returns_archive_csv_scope_and_no_gl_writes(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, rents, archived, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        before = db.query(GLEntry).count()
        payload = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        assert len(payload.rows) == 4
        assert [row[-1] for row in payload.rows[:3]] == [
            Decimal("100"), Decimal("-25"), Decimal("10"),
        ]
        assert payload.rows[-1][8:] == (
            Decimal("25"), Decimal("110"), Decimal("85"),
        )
        assert [row[5] for row in payload.rows[:3]] == ["4100", "4100", "4200"]
        only_rents = _report(db, admin, date_from="2026-09-01",
                              date_to="2026-09-30", account_id=rents.id)
        assert len(only_rents.rows) == 3
        assert "cash-basis" in payload.title.lower()
        csv = report_csv_bytes(payload).decode("utf-8-sig")
        assert "'=Recorded income" in csv and "'=R-1" in csv
        assert "'=Income 4100" in csv
        assert "5555" not in csv and "999" not in csv
        assert db.query(GLEntry).count() == before
    finally:
        db.close()
        engine.dispose()


def test_dates_roles_org_and_cash_basis_refused(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, rents, archived, foreign_income = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        for params in ({}, {"date_from": "2026-09-01"},
                       {"date_from": "2026-10-01", "date_to": "2026-09-01"},
                       {"date_from": "bad", "date_to": "2026-09-01"},
                       {"date_from": "2026-09-01", "date_to": "2026-09-30",
                        "account_id": foreign_income.id},
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
        db.close()
        engine.dispose()


def test_catalog_preview_email_csv_gate_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.href == "/dashboard/reporting/income-register"
        assert item.presentation == "BUTTON"
        assert router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"date_from": "2026-09-01", "date_to": "2026-09-30"})
        response = Response()
        result = router.preview_income_register(req, response, db=db, current_user=admin)
        assert result["total"] == 4 and response.headers["cache-control"] == "no-store"
        exported = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Signed Net Income" in exported.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        outcome = router.email_report(
            KEY, router.ReportEmailIn(recipient="finance@example.com",
                                      parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert outcome.sent and b"5555" not in sent["attachments"][0][1]
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            router.preview_income_register(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
