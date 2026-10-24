"""Deposit Register verifies receipt groupings, not additional cash GL postings."""
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
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.receipt import Receipt
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services import deposit_register as register
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)

KEY = "transaction.deposit_register"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Deposit Register One", slug="deposit-register-one")
    two = Organization(name="Deposit Register Two", slug="deposit-register-two")
    db.add_all([one, two]); db.flush()

    def user(org, role, name):
        obj = User(
            organization_id=org.id, role=role, first_name=name, last_name="Deposit",
            email=f"{name}@deposit-register.example", hashed_password="x", is_active=True,
        )
        db.add(obj); db.flush(); return obj

    admin = user(one, UserRole.ADMIN, "DepositAdmin")
    manager = user(one, UserRole.MANAGER, "DepositManager")
    foreign_admin = user(two, UserRole.ADMIN, "DepositForeign")

    def gl(org, number, name):
        obj = GLAccount(
            organization_id=org.id, gl_number=number, name=name,
            account_type="ASSET", is_active=True,
        )
        db.add(obj); db.flush(); return obj

    cash = gl(one, "1160", "=Deposit Cash")
    foreign_cash = gl(two, "1160", "Foreign Cash")
    today = date.today()

    def receipt(org, acct, number, amount, reversed_=False):
        obj = Receipt(
            organization_id=org.id, type="OTHER", receipt_date=today,
            amount=Decimal(amount), cash_gl_account_id=acct.id,
            reference_number=number, is_reversed=reversed_, is_active=True,
        )
        db.add(obj); db.flush()
        txn = GLTransaction(
            organization_id=org.id, transaction_date=today,
            transaction_type="RECEIPT", source_type="receipt", source_id=obj.id,
            is_reversed=reversed_,
        )
        db.add(txn); db.flush()
        obj.gl_transaction_id = txn.id
        return obj

    first = receipt(one, cash, "R-1", "40")
    second = receipt(one, cash, "R-2", "60", reversed_=True)
    foreign = receipt(two, foreign_cash, "R-F", "999")
    deposit = Deposit(
        organization_id=one.id, bank_gl_account_id=cash.id,
        deposit_date=today, deposit_number="=D-22",
        total=Decimal("100"), description="=Bulk receipts", is_active=True,
    )
    foreign_deposit = Deposit(
        organization_id=two.id, bank_gl_account_id=foreign_cash.id,
        deposit_date=today, deposit_number="D-F",
        total=Decimal("999"), description="Foreign only", is_active=True,
    )
    db.add_all([deposit, foreign_deposit]); db.flush()
    first_line = DepositLine(
        organization_id=one.id, deposit_id=deposit.id, receipt_id=first.id,
    )
    second_line = DepositLine(
        organization_id=one.id, deposit_id=deposit.id, receipt_id=second.id,
    )
    db.add_all([
        first_line, second_line,
        DepositLine(organization_id=two.id, deposit_id=foreign_deposit.id,
                    receipt_id=foreign.id),
    ])
    db.commit()
    return admin, manager, foreign_admin, cash, foreign_cash, deposit, foreign_deposit, first, second, foreign, first_line, second_line


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=params,
    )


def test_posted_receipt_grouping_reversal_and_csv_isolation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign_admin, cash, _, deposit, _, first, second, _, _, _ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        before = db.query(GLTransaction).count()
        result = _report(db, admin)
        assert len(result.rows) == 1
        row = result.rows[0]
        assert row[0] == deposit.id and row[5] == Decimal("100")
        assert row[6] == 2 and row[7] == 1
        assert row[9] == "REVERSED RECEIPTS PRESENT"
        assert len(_report(db, admin, bank_gl_account_id=cash.id).rows) == 1
        assert len(_report(db, admin, date_from=date.today().isoformat(),
                           date_to=date.today().isoformat()).rows) == 1
        csv = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=Deposit Cash" in csv and "'=Bulk receipts" in csv and "'=D-22" in csv
        assert "Foreign only" not in csv and "999" not in csv
        assert "not a new gl" in result.title.lower()
        assert db.query(GLTransaction).count() == before
    finally:
        db.close(); engine.dispose()


def test_invalid_org_reference_and_recorded_total_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign_admin, cash, foreign_cash, deposit, other, first, second, foreign, first_line, second_line = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, manager)
        for params in (
            {"deposit_id": other.id}, {"bank_gl_account_id": foreign_cash.id},
            {"deposit_id": -1}, {"sql": "SELECT * FROM tax_profiles"},
            {"date_from": "2026-10-01", "date_to": "2026-09-01"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        assert len(_report(db, foreign_admin).rows) == 1
        deposit.total = Decimal("55"); db.flush()
        with pytest.raises(ReportDeliveryError, match="totals disagree"):
            _report(db, admin)
        deposit.total = Decimal("100")
        second_line.receipt_id = foreign.id; db.flush()
        with pytest.raises(ReportDeliveryError, match="receipt organization"):
            _report(db, admin)
        second_line.receipt_id = second.id
        first_line.organization_id = foreign_admin.organization_id; db.flush()
        with pytest.raises(ReportDeliveryError, match="line organization"):
            _report(db, admin)
        first_line.organization_id = admin.organization_id
        first.cash_gl_account_id = foreign_cash.id; db.flush()
        with pytest.raises(ReportDeliveryError, match="cash GL mapping"):
            _report(db, admin)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_catalog_preview_export_email_and_rechecks(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.href == "/dashboard/reporting/deposit-register"
        assert item.presentation == "BUTTON"
        assert router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.DEPOSITS"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)],
        )
        req = SimpleNamespace(query_params={})
        response = Response()
        data = router.preview_deposit_register(req, response, db=db, current_user=admin)
        assert data["total"] == 1
        assert response.headers["cache-control"] == "no-store"
        csv = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Recorded Grouping Total" in csv.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        outcome = router.email_report(
            KEY, router.ReportEmailIn(recipient="finance@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert outcome.sent
        assert b"Foreign only" not in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_deposit_register(req, Response(), db=db, current_user=admin)
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
