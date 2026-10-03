"""Posted account totals keep the GL immutable and reject CASH mislabeling."""
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

KEY = "accounting.account_totals"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Totals One", slug="account-totals-one")
    other = Organization(name="Totals Other", slug="account-totals-two")
    db.add_all([org, other]); db.flush()
    def person(o, role, name):
        row = User(organization_id=o.id, role=role, first_name=name,
                   last_name="Accountant", email=f"{name.lower()}@totals.example",
                   hashed_password="x", is_active=True)
        db.add(row); db.flush(); return row
    admin = person(org, UserRole.ADMIN, "Admin")
    owner = person(org, UserRole.OWNER, "Owner")
    manager = person(org, UserRole.MANAGER, "Manager")
    foreign = person(other, UserRole.ADMIN, "Foreign")
    def acct(o, number, name, kind, active=True):
        row = GLAccount(organization_id=o.id, gl_number=number,
                        name=name, account_type=kind, is_active=active)
        db.add(row); db.flush(); return row
    asset = acct(org, "1000", "=Bank", "ASSET")
    income = acct(org, "4000", "Income", "INCOME", active=False)
    unused = acct(org, "5000", "Unused", "EXPENSE")
    foreign_asset = acct(other, "9999", "Other Org Secret", "ASSET")
    def posting(o, when, debits, credits):
        tx = GLTransaction(organization_id=o.id, transaction_date=when,
                           transaction_type="JOURNAL_ENTRY")
        db.add(tx); db.flush()
        for acc, value in debits:
            db.add(GLEntry(organization_id=o.id, transaction_id=tx.id,
                           gl_account_id=acc.id, debit=Decimal(value), credit=Decimal("0")))
        for acc, value in credits:
            db.add(GLEntry(organization_id=o.id, transaction_id=tx.id,
                           gl_account_id=acc.id, debit=Decimal("0"), credit=Decimal(value)))
        db.flush()
    posting(org, date(2026, 8, 1), [(asset, "100.00")], [(income, "100.00")])
    posting(org, date(2026, 9, 1), [(income, "40.00")], [(asset, "40.00")])
    posting(other, date(2026, 9, 1), [(foreign_asset, "777.00")], [(foreign_asset, "777.00")])
    db.commit()
    return admin, owner, manager, foreign, asset, income, unused


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        parameters=params, current_user=actor,
    )


def test_posted_debit_credit_and_real_reversal_inactive_account(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, asset, income, unused = _seed(db)
        monkeypatch.setattr(account_totals, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        rows = _payload(db, admin).rows
        assert len(rows) == 2
        assert rows[0][0] == "1000"
        assert rows[0][3:] == (Decimal("100.00"), Decimal("40.00"), Decimal("60.00"))
        assert rows[1][0] == "4000"
        assert rows[1][3:] == (Decimal("40.00"), Decimal("100.00"), Decimal("-60.00"))
        assert len(_payload(db, admin, as_of="2026-08-01").rows) == 2
        assert _payload(db, admin, as_of="2026-08-01").rows[0][-1] == Decimal("100.00")
        assert len(_payload(db, admin, include_zero="true").rows) == 3
        csv = report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert "'=Bank" in csv
        assert "Other Org Secret" not in csv
        assert db.query(GLEntry).count() == before
    finally:
        db.close(); engine.dispose()


def test_admin_permission_and_cash_mode_refusal(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, *_ = _seed(db)
        monkeypatch.setattr(account_totals, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor)
        assert len(_payload(db, foreign).rows) == 1
        for params in ({"sql": "SELECT * FROM users"}, {"as_of": "yesterday"},
                       {"include_zero": "definitely"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        settings = AccountingSettings(organization_id=admin.organization_id,
                                      accounting_basis="CASH")
        db.add(settings); db.commit()
        with pytest.raises(ReportDeliveryError, match="CASH"):
            _payload(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_gate_rechecks(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(account_totals, "permission_allows_user", lambda *a, **k: True)
        entry = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert entry.presentation == "BUTTON"
        assert entry.href == "/dashboard/reporting/account-totals"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={})
        response = Response()
        data = report_router.preview_account_totals(req, response, db=db, current_user=admin)
        assert data["total"] == 2
        assert response.headers["cache-control"] == "no-store"
        assert b"Net Debit Minus Credit" in report_router.export_report_csv(
            KEY, req, db=db, current_user=admin).body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(recipient="admin@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert result.sent and b"account-totals" in sent["attachments"][0][0].encode()
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_account_totals(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
