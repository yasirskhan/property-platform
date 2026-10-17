"""Trust detail is posted book GL with organization-validated recorded tags."""
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
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property
from app.models.user import Organization, User, UserRole
from app.services import trust_account_balance as trust_balance
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as reporting_router

KEY = "accounting.trust_account_detail"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Trust Detail One", slug="trust-detail-one")
    second = Organization(name="Trust Detail Two", slug="trust-detail-two")
    db.add_all([first, second]); db.flush()
    def user(org, role, name):
        u = User(organization_id=org.id, role=role,
                 email=f"{name}@trust-detail.example", first_name=name,
                 last_name="Detail", hashed_password="x", is_active=True)
        db.add(u); db.flush(); return u
    admin = user(first, UserRole.ADMIN, "admin")
    owner = user(first, UserRole.OWNER, "owner")
    manager = user(first, UserRole.MANAGER, "manager")
    foreign_admin = user(second, UserRole.ADMIN, "foreignadmin")
    foreign_owner = user(second, UserRole.OWNER, "foreignowner")
    def property_(org, name):
        p = Property(organization_id=org.id, name=name,
                     address_line1="100 Recorded Street", city="Cleveland",
                     state="OH", zip_code="44113", country="USA")
        db.add(p); db.flush(); return p
    prop = property_(first, "Assigned Trust Property")
    foreign_prop = property_(second, "SECRET FOREIGN PROPERTY")
    def account(org, number):
        row = GLAccount(organization_id=org.id, gl_number=number,
                        name=f"Cash {number}", account_type="ASSET")
        db.add(row); db.flush(); return row
    cash = account(first, "1150")
    foreign_cash = account(second, "9999")
    def bank(org, acct, name):
        row = BankAccount(organization_id=org.id, gl_account_id=acct.id,
                          account_type="OPERATING", name=name,
                          routing_number="123456789",
                          account_number="SECRET-ACCOUNT")
        db.add(row); db.flush(); return row
    trust = bank(first, cash, "=Trust Bank")
    outsider = bank(second, foreign_cash, "Foreign Bank")
    def entry(org, when, gl, debit, credit, reference="", property_id=None, owner_id=None):
        txn = GLTransaction(organization_id=org.id, transaction_type="JOURNAL_ENTRY",
                            transaction_date=when, reference_number=reference)
        db.add(txn); db.flush()
        db.add(GLEntry(organization_id=org.id, transaction_id=txn.id,
                       gl_account_id=gl.id, debit=Decimal(debit),
                       credit=Decimal(credit), property_id=property_id, owner_id=owner_id))
        db.flush()
    entry(first, date(2026, 8, 30), cash, "100", "0", "PREVIOUS")
    entry(first, date(2026, 9, 1), cash, "0", "30", "=REVERSAL", prop.id, owner.id)
    entry(first, date(2026, 9, 2), cash, "20", "0", "BAD TAGS", foreign_prop.id, foreign_owner.id)
    entry(first, date(2026, 9, 3), cash, "15", "0", "UNTAGGED")
    entry(first, date(2026, 10, 1), cash, "777", "0", "LATER")
    entry(second, date(2026, 9, 1), foreign_cash, "9999", "0", "FOREIGN")
    db.commit()
    return admin, owner, manager, foreign_admin, prop, foreign_prop, trust, outsider, foreign_cash


def _report(db, actor, **params):
    return build_report_payload(db, organization_id=actor.organization_id,
                                current_user=actor, report_key=KEY, parameters=params)


def test_opening_running_and_validated_owner_property_tags_no_foreign_leaks(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, _, _, prop, foreign_prop, bank, _, _ = _seed(db)
        monkeypatch.setattr(trust_balance, "permission_allows_user", lambda *a, **k: True)
        bank.is_active = False
        db.flush()
        before = db.query(GLEntry).count()
        detail = _report(db, admin, bank_id=bank.id,
                         date_from="2026-09-01", date_to="2026-09-30")
        assert len(detail.rows) == 5
        assert detail.rows[0][0] == "OPENING" and detail.rows[0][9] == Decimal("100")
        assert detail.rows[1][7:10] == (Decimal("0"), Decimal("30"), Decimal("70"))
        assert detail.rows[1][5:7] == (prop.id, owner.id)
        assert "RECORDED" in detail.rows[1][10]
        assert detail.rows[2][5:7] == ("", "")
        assert "PROPERTY TAG UNVERIFIED" in detail.rows[2][-1]
        assert "OWNER TAG UNVERIFIED" in detail.rows[2][-1]
        assert detail.rows[2][9] == Decimal("90")
        assert detail.rows[3][9] == Decimal("105")
        assert "UNALLOCATED" in detail.rows[3][-1]
        assert detail.rows[-1][0] == "CLOSING" and detail.rows[-1][9] == Decimal("105")
        csv_text = report_csv_bytes(detail).decode("utf-8-sig")
        assert "'=REVERSAL" in csv_text
        for secret in ("SECRET-ACCOUNT", "123456789", "SECRET FOREIGN PROPERTY",
                       "9999", "777", "FOREIGN"):
            assert secret not in csv_text
        assert db.query(GLEntry).count() == before
        empty = _report(db, admin, bank_id=bank.id,
                        date_from="2026-09-10", date_to="2026-09-15")
        assert len(empty.rows) == 2
        assert empty.rows[0][9] == Decimal("105")
        assert empty.rows[1][9] == Decimal("105")
    finally:
        db.close(); engine.dispose()


def test_invalid_filters_role_org_scope_and_foreign_mapping(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, prop, foreign_prop, bank, other, foreign_cash = _seed(db)
        monkeypatch.setattr(trust_balance, "permission_allows_user", lambda *a, **k: True)
        args = dict(bank_id=bank.id, date_from="2026-09-01", date_to="2026-09-30")
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor, **args)
        for params in (
            {}, {"bank_id": bank.id}, {"bank_id": bank.id, "date_from": "2026-09-01"},
            {"bank_id": "invalid", "date_from": "2026-09-01", "date_to": "2026-09-30"},
            {"bank_id": -1, "date_from": "2026-09-01", "date_to": "2026-09-30"},
            {"bank_id": bank.id, "date_from": "bad", "date_to": "2026-09-30"},
            {"bank_id": bank.id, "date_from": "2026-10-01", "date_to": "2026-09-30"},
            {"bank_id": bank.id, "date_from": "2026-09-01", "date_to": "2026-09-30",
             "sql": "SELECT * FROM users"},
            {"bank_id": other.id, "date_from": "2026-09-01", "date_to": "2026-09-30"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        foreign_detail = _report(db, foreign, bank_id=other.id,
                                 date_from="2026-09-01", date_to="2026-09-30")
        assert foreign_detail.rows[1][9] == Decimal("9999")
        monkeypatch.setattr(trust_balance, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, **args)
        monkeypatch.setattr(trust_balance, "permission_allows_user", lambda *a, **k: True)
        bank.gl_account_id = foreign_cash.id
        db.flush()
        with pytest.raises(ReportDeliveryError, match="mapping"):
            _report(db, admin, **args)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, _, _, bank, _, _ = _seed(db)
        monkeypatch.setattr(trust_balance, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "TAB"
        assert item.href == "/dashboard/reporting/trust-account-detail"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={
            "bank_id": str(bank.id), "date_from": "2026-09-01",
            "date_to": "2026-09-30",
        })
        response = Response()
        preview = reporting_router.preview_trust_account_detail(
            req, response, db=db, current_user=admin,
        )
        assert preview["total"] == 5
        assert response.headers["cache-control"] == "no-store"
        csv_response = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Running Posted Book Balance" in csv_response.body
        assert b"SECRET-ACCOUNT" not in csv_response.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email",
                            lambda **kwargs: sent.update(kwargs))
        result = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="bookkeeper@example.com",
                parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert result.sent and b"SECRET-ACCOUNT" not in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_trust_account_detail(
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
