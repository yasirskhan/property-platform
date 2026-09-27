"""Trust account book balances must not pretend to reconcile statements or owners."""
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
from app.models.user import Organization, User, UserRole
from app.services import trust_account_balance as trust
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as reporting_router

KEY = "accounting.trust_account_balance"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Trust Org", slug="trust-org")
    second = Organization(name="Foreign Trust Org", slug="foreign-trust-org")
    db.add_all([first, second]); db.flush()
    def user(org, role, tag):
        u = User(organization_id=org.id, role=role,
                 email=f"{tag}@trust.example", first_name=tag.title(),
                 last_name="Trust", hashed_password="x", is_active=True)
        db.add(u); db.flush(); return u
    admin = user(first, UserRole.ADMIN, "admin")
    manager = user(first, UserRole.MANAGER, "manager")
    owner = user(first, UserRole.OWNER, "owner")
    foreign = user(second, UserRole.ADMIN, "foreign")
    def account(org, number, kind="ASSET", **kw):
        gl = GLAccount(organization_id=org.id, gl_number=number,
                       name=f"GL {number}", account_type=kind, **kw)
        db.add(gl); db.flush(); return gl
    operating = account(first, "=1150")
    escrow = account(first, "1160", is_active=False)
    foreign_gl = account(second, "9999")
    nonasset = account(first, "2101", "LIABILITY")
    def bank(org, name, gl, kind="OPERATING", **kw):
        b = BankAccount(organization_id=org.id, name=name, bank_name="PRIVATE",
                        routing_number="000000999", account_number="SECRET12345",
                        gl_account_id=gl.id, account_type=kind, **kw)
        db.add(b); db.flush(); return b
    trust_one = bank(first, "=Operating Trust", operating)
    trust_two = bank(first, "Security Deposit Trust", escrow, "ESCROW", is_active=False)
    other = bank(second, "Foreign Trust", foreign_gl)
    def entry(org, day, gl, debit, credit):
        tx = GLTransaction(organization_id=org.id, transaction_date=day,
                           transaction_type="JOURNAL_ENTRY")
        db.add(tx); db.flush()
        db.add(GLEntry(organization_id=org.id, transaction_id=tx.id,
                       gl_account_id=gl.id, debit=Decimal(debit),
                       credit=Decimal(credit)))
        db.flush()
    entry(first, date(2026, 8, 31), operating, "1000", "0")
    entry(first, date(2026, 9, 1), operating, "100", "0")
    entry(first, date(2026, 9, 2), operating, "0", "20")
    entry(first, date(2026, 9, 3), escrow, "400", "0")
    entry(first, date(2026, 9, 4), escrow, "0", "25")
    entry(first, date(2026, 10, 1), operating, "777", "0")
    entry(second, date(2026, 9, 1), foreign_gl, "99999", "0")
    db.commit()
    return admin, manager, owner, foreign, trust_one, trust_two, other, nonasset, operating


def _report(db, actor, **params):
    return build_report_payload(db, organization_id=actor.organization_id,
                                current_user=actor, report_key=KEY, parameters=params)


def test_historical_posted_balances_reversals_archives_and_no_private_bank_fields(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, operating, escrow, _, _, _ = _seed(db)
        monkeypatch.setattr(trust, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        result = _report(db, admin, as_of="2026-09-30")
        assert len(result.rows) == 3
        rows = {row[0]: row for row in result.rows}
        assert rows[operating.id][-1] == Decimal("1080")
        assert rows[escrow.id][-1] == Decimal("375")
        assert rows[escrow.id][3] == "ARCHIVED"
        assert rows[escrow.id][5] == "ARCHIVED"
        assert rows["TOTAL"][-1] == Decimal("1455")
        text = report_csv_bytes(result).decode("utf-8-sig")
        for private in ("SECRET12345", "000000999", "99999", "777", "PRIVATE"):
            assert private not in text
        assert "'=Operating Trust" in text
        assert db.query(GLEntry).count() == before
        early = _report(db, admin, as_of="2026-08-30")
        assert early.rows[-1][-1] == Decimal("0")
        single = _report(db, admin, as_of="2026-09-30",
                         bank_id=str(escrow.id))
        assert len(single.rows) == 2 and single.rows[-1][-1] == Decimal("375")
    finally:
        db.close(); engine.dispose()


def test_scope_permissions_invalid_mapping_and_duplicate_guard(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, owner, foreign, bank, escrow, other, nonasset, operating = _seed(db)
        monkeypatch.setattr(trust, "permission_allows_user", lambda *a, **k: True)
        for actor in (manager, owner):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor, as_of="2026-09-30")
        for params in (
            {}, {"as_of": "bad"}, {"as_of": "2026-09-30", "sql": "select"},
            {"as_of": "2026-09-30", "bank_id": "-1"},
            {"as_of": "2026-09-30", "bank_id": "oops"},
            {"as_of": "2026-09-30", "bank_id": str(other.id)},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        other_result = _report(db, foreign, as_of="2026-09-30")
        assert other_result.rows[-1][-1] == Decimal("99999")
        monkeypatch.setattr(trust, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, as_of="2026-09-30")
        monkeypatch.setattr(trust, "permission_allows_user", lambda *a, **k: True)
        escrow.gl_account_id = nonasset.id
        db.flush()
        with pytest.raises(ReportDeliveryError, match="mapping"):
            _report(db, admin, as_of="2026-09-30")
        escrow.gl_account_id = operating.id
        db.flush()
        with pytest.raises(ReportDeliveryError, match="Duplicate"):
            _report(db, admin, as_of="2026-09-30", bank_id=str(bank.id))
        escrow.gl_account_id = other.gl_account_id
        db.flush()
        with pytest.raises(ReportDeliveryError, match="mapping"):
            _report(db, admin, as_of="2026-09-30")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_catalog_preview_export_email_revocation_and_no_gl_writes(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(trust, "permission_allows_user", lambda *a, **k: True)
        item = next(r for r in REPORT_CATALOG if r.key == KEY)
        assert item.presentation == "TAB"
        assert item.href == "/dashboard/reporting/trust-account-balance"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"as_of": "2026-09-30"})
        n = db.query(GLEntry).count()
        response = Response()
        preview = reporting_router.preview_trust_account_balance(
            req, response, db=db, current_user=admin,
        )
        assert preview["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        exported = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Posted GL Book Balance" in exported.body
        assert b"SECRET12345" not in exported.body
        mailed = {}
        monkeypatch.setattr(reporting_router, "send_email",
                            lambda **kwargs: mailed.update(kwargs))
        outcome = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="accountant@example.com", parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert outcome.sent and b"SECRET12345" not in mailed["attachments"][0][1]
        assert db.query(GLEntry).count() == n
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_trust_account_balance(
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
