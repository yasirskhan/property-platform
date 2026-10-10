"""Check Register Detail preserves posted check scope and recorded allocations."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.bill import Bill
from app.models.check import Check, CheckBillAllocation
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services import check_register_report as register
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)

KEY = "transaction.check_register_detail"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Check Detail Org", slug="check-detail-org")
    other = Organization(name="Foreign Check Detail", slug="foreign-check-detail")
    db.add_all([org, other])
    db.flush()

    def user(o, role, first):
        obj = User(organization_id=o.id, role=role, first_name=first,
                   last_name="Checks", email=f"{first}@checkdetail.example",
                   hashed_password="x", is_active=True)
        db.add(obj)
        db.flush()
        return obj

    admin = user(org, UserRole.ADMIN, "DetailAdmin")
    manager = user(org, UserRole.MANAGER, "DetailManager")
    foreign = user(other, UserRole.ADMIN, "DetailForeign")

    def cash(o, number, name):
        obj = GLAccount(organization_id=o.id, gl_number=number,
                        name=name, account_type="ASSET", is_active=True)
        db.add(obj)
        db.flush()
        return obj

    cash_gl = cash(org, "1175", "Cash")
    other_cash_gl = cash(other, "1175", "Foreign Cash")
    payable_gl = GLAccount(organization_id=org.id, gl_number="2105",
                           name="Payables", account_type="LIABILITY", is_active=True)
    db.add(payable_gl)
    db.flush()

    def bank(o, gl, name):
        obj = BankAccount(
            organization_id=o.id, gl_account_id=gl.id, name=name,
            account_type="OPERATING", routing_number="021000021",
            account_number="12345678901234567890", is_active=True,
        )
        db.add(obj)
        db.flush()
        return obj

    local_bank = bank(org, cash_gl, "=Operating")
    foreign_bank = bank(other, other_cash_gl, "Foreign bank")
    today = date.today()
    bills = []
    for num, amount in (("=INV1", "40"), ("INV2", "60")):
        bill = Bill(
            organization_id=org.id, payee_name="=Vendor",
            bill_date=today, amount=Decimal(amount), amount_paid=Decimal(amount),
            payable_gl_account_id=payable_gl.id, status="PAID",
            bill_number=num, is_active=True, is_reversed=False,
        )
        db.add(bill)
        db.flush()
        bills.append(bill)
    foreign_bill = Bill(
        organization_id=other.id, payee_name="Private Vendor",
        bill_date=today, amount=Decimal("999"), amount_paid=Decimal("999"),
        payable_gl_account_id=other_cash_gl.id, status="PAID",
    )
    db.add(foreign_bill)
    db.flush()

    check = Check(organization_id=org.id, bank_account_id=local_bank.id,
                  check_number="CHK-100", check_date=today,
                  payee_name="=Vendor", amount=Decimal("100"), status="ISSUED")
    db.add(check)
    db.flush()
    issue = GLTransaction(
        organization_id=org.id, transaction_date=today,
        transaction_type="CHECK", source_type="check", source_id=check.id,
        is_reversed=False,
    )
    db.add(issue)
    db.flush()
    check.gl_transaction_id = issue.id
    allocations = []
    for bill in bills:
        obj = CheckBillAllocation(check_id=check.id, bill_id=bill.id, amount=bill.amount)
        db.add(obj)
        allocations.append(obj)
    db.commit()
    return admin, manager, foreign, local_bank, foreign_bank, check, bills, foreign_bill, allocations, issue


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=params,
    )


def test_check_header_once_allocations_and_bank_secrets_excluded(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, bank, _, check, bills, _, allocations, issue = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        before = db.query(GLTransaction).count()
        report = _report(db, admin)
        assert [row[0] for row in report.rows] == ["CHECK", "ALLOCATION", "ALLOCATION"]
        assert report.rows[0][7] == Decimal("100")
        assert report.rows[0][11] == issue.id
        assert report.rows[1][7] == "" and report.rows[2][7] == ""
        assert [row[10] for row in report.rows[1:]] == [Decimal("40"), Decimal("60")]
        assert [row[8] for row in report.rows[1:]] == [bills[0].id, bills[1].id]
        assert len(_report(db, admin, check_id=check.id, bank_id=bank.id).rows) == 3
        csv = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Vendor" in csv and "'=INV1" in csv and "'=Operating" in csv
        for secret in ("021000021", "12345678901234567890", "Private Vendor"):
            assert secret not in csv
        assert "not cleared" in report.title.lower()
        assert db.query(GLTransaction).count() == before
    finally:
        db.close()
        engine.dispose()


def test_foreign_allocation_and_mismatched_total_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, bank, foreign_bank, check, bills, foreign_bill, allocations, issue = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        for actor in (manager,):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor)
        for filters in ({"check_id": 999999}, {"bank_id": foreign_bank.id},
                        {"status": "CLEARED"}, {"check_id": -1},
                        {"sql": "SELECT * FROM tax_profiles"}):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **filters)
        allocations[1].bill_id = foreign_bill.id
        db.flush()
        with pytest.raises(ReportDeliveryError, match="allocation bill"):
            _report(db, admin)
        allocations[1].bill_id = bills[1].id
        allocations[1].amount = Decimal("10")
        db.flush()
        with pytest.raises(ReportDeliveryError, match="totals disagree"):
            _report(db, admin)
        allocations[1].amount = Decimal("60")
        allocations[1].amount = Decimal("-1")
        db.flush()
        with pytest.raises(ReportDeliveryError, match="Invalid recorded"):
            _report(db, admin)
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_catalog_preview_export_email_and_release_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.href == "/dashboard/reporting/check-register-detail"
        assert item.presentation == "BUTTON"
        assert router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)],
        )
        req = SimpleNamespace(query_params={})
        response = Response()
        data = router.preview_check_register_detail(req, response, db=db, current_user=admin)
        assert data["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        csv = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Recorded Allocation Amount" in csv.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        outcome = router.email_report(
            KEY, router.ReportEmailIn(recipient="audit@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert outcome.sent
        assert b"12345678901234567890" not in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_check_register_detail(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(
            router, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL",
        )
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
