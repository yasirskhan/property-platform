"""Bank activity is scoped posted cash GL, not private bank data or imported feed."""
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
from app.models.bank_account import BankAccount
from app.models.bank_feed import BankFeedTransaction
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.services import bank_account_activity as activity
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "accounting.bank_activity"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Bank Book One", slug="bank-book-one")
    other = Organization(name="Bank Book Two", slug="bank-book-two")
    db.add_all([org, other]); db.flush()
    def person(o, role, name):
        u = User(organization_id=o.id, role=role, first_name=name,
                 last_name="Book", email=f"{name.lower()}@bankbook.example",
                 hashed_password="x", is_active=True)
        db.add(u); db.flush(); return u
    admin = person(org, UserRole.ADMIN, "Admin")
    owner = person(org, UserRole.OWNER, "Owner")
    manager = person(org, UserRole.MANAGER, "Manager")
    foreign_admin = person(other, UserRole.ADMIN, "Foreign")
    def account(o, number):
        a = GLAccount(organization_id=o.id, gl_number=number,
                      name="Book Cash", account_type="ASSET")
        db.add(a); db.flush(); return a
    cash = account(org, "1150")
    another = account(org, "1160")
    foreign_cash = account(other, "9999")
    def bank(o, a, name, num):
        x = BankAccount(organization_id=o.id, name=name, gl_account_id=a.id,
                        account_type="OPERATING",
                        routing_number="010203040", account_number=num)
        db.add(x); db.flush(); return x
    bank_one = bank(org, cash, "Client Trust", "PRIVATE-ACCOUNT-9876")
    bank_two = bank(org, another, "Deposit Trust", "PRIVATE-ACCOUNT-1234")
    other_bank = bank(other, foreign_cash, "Other Bank", "FOREIGN-PRIVATE")
    def tx(o, when, gl, debit, credit, reference):
        t = GLTransaction(organization_id=o.id, transaction_date=when,
                          transaction_type="JOURNAL_ENTRY", reference_number=reference)
        db.add(t); db.flush()
        row = GLEntry(organization_id=o.id, transaction_id=t.id,
                      gl_account_id=gl.id,
                      debit=Decimal(debit), credit=Decimal(credit))
        db.add(row); db.flush()
        return row
    tx(org, date(2026, 8, 1), cash, "100.00", "0", "OPENING")
    tx(org, date(2026, 9, 1), cash, "0", "25.00", "=Reversal")
    tx(org, date(2026, 9, 2), cash, "12.00", "0", "RETURN")
    tx(org, date(2026, 9, 1), another, "777.00", "0", "UNRELATED")
    tx(other, date(2026, 9, 1), foreign_cash, "999.00", "0", "FOREIGN")
    db.add(BankFeedTransaction(
        organization_id=org.id, bank_account_id=bank_one.id,
        source_provider="CSV", import_key="x" * 64,
        posted_date=date(2026, 9, 3),
        amount=Decimal("444.00"), payee="UNPOSTED IMPORT",
    ))
    db.commit()
    return admin, owner, manager, foreign_admin, bank_one, bank_two, other_bank, cash


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        current_user=actor, parameters=params,
    )


def test_dated_running_gl_book_and_privacy(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, bank, bank2, other_bank, cash = _seed(db)
        monkeypatch.setattr(activity, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        report = _payload(db, admin, bank_id=bank.id, date_from="2026-09-01", date_to="2026-09-02")
        assert len(report.rows) == 3
        assert report.rows[0][-1] == Decimal("100.00")
        assert report.rows[1][-1] == Decimal("75.00")
        assert report.rows[2][-1] == Decimal("87.00")
        csv = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Reversal" in csv
        for forbidden in ("PRIVATE-ACCOUNT-9876", "010203040", "FOREIGN-PRIVATE",
                          "UNPOSTED IMPORT", "UNRELATED", "FOREIGN"):
            assert forbidden not in csv
        assert len(_payload(db, admin, bank_id=bank2.id).rows) == 2
        assert db.query(GLEntry).count() == before
    finally:
        db.close(); engine.dispose()


def test_roles_cross_org_and_cash_mode_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, bank, bank2, other_bank, cash = _seed(db)
        monkeypatch.setattr(activity, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor, bank_id=bank.id)
        with pytest.raises(ReportDeliveryError, match="Bank account not found"):
            _payload(db, admin, bank_id=other_bank.id)
        with pytest.raises(ReportDeliveryError, match="Bank account not found"):
            _payload(db, foreign, bank_id=bank.id)
        for params in ({}, {"bank_id": "abc"}, {"bank_id": "-1"},
                       {"bank_id": bank.id, "sql": "SELECT * FROM users"},
                       {"bank_id": bank.id, "date_to": "bad"},
                       {"bank_id": bank.id, "date_from": "2026-09-02", "date_to": "2026-09-01"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        monkeypatch.setattr(
            activity, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS",
        )
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin, bank_id=bank.id)
        monkeypatch.setattr(activity, "permission_allows_user", lambda *a, **k: True)
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _payload(db, admin, bank_id=bank.id)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, bank, *_ = _seed(db)
        monkeypatch.setattr(activity, "permission_allows_user", lambda *a, **k: True)
        entry = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert entry.presentation == "BUTTON"
        assert entry.href == "/dashboard/reporting/bank-activity"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"bank_id": str(bank.id)})
        response = Response()
        data = report_router.preview_bank_account_activity(req, response, db=db, current_user=admin)
        assert data["total"] == 4
        assert response.headers["cache-control"] == "no-store"
        assert "PRIVATE-ACCOUNT" not in str(data)
        result = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Running GL Book Balance" in result.body
        assert b"PRIVATE-ACCOUNT" not in result.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="staff@example.com", parameters={"bank_id": bank.id}),
            db=db, current_user=admin,
        )
        assert result.sent and b"PRIVATE-ACCOUNT" not in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_bank_account_activity(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
