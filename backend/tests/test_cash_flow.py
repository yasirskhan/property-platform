"""Cash Flow uses posted mapped cash GL movements without invented categories."""
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
from app.services import cash_flow as cash_service
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as reporting_router

KEY = "accounting.cash_flow"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Cash Flow One", slug="cash-flow-one")
    other = Organization(name="Cash Flow Other", slug="cash-flow-other")
    db.add_all([org, other]); db.flush()
    def actor(o, role, name):
        u = User(organization_id=o.id, role=role, first_name=name, last_name="Cash",
                 email=f"{name.lower()}@cash-movement.example",
                 hashed_password="x", is_active=True)
        db.add(u); db.flush(); return u
    admin = actor(org, UserRole.ADMIN, "Admin")
    owner = actor(org, UserRole.OWNER, "Owner")
    manager = actor(org, UserRole.MANAGER, "Manager")
    foreign = actor(other, UserRole.ADMIN, "Foreign")

    def gl(o, number, **extra):
        g = GLAccount(organization_id=o.id, gl_number=number, name=f"Cash {number}",
                      account_type="ASSET", **extra)
        db.add(g); db.flush(); return g
    primary_gl = gl(org, "1150")
    secondary_gl = gl(org, "1160", is_active=False)
    excluded_gl = gl(org, "1170", include_on_cash_flow=False)
    unlinked_gl = gl(org, "1180")
    outside_gl = gl(other, "9999")
    def bank(o, linked, name, **extra):
        b = BankAccount(organization_id=o.id, gl_account_id=linked.id, name=name,
                        account_type="OPERATING", account_number="TOP-SECRET-0001",
                        routing_number="010203040", **extra)
        db.add(b); db.flush(); return b
    primary = bank(org, primary_gl, "Primary")
    secondary = bank(org, secondary_gl, "=Old Trust", is_active=False)
    excluded = bank(org, excluded_gl, "Excluded")
    foreign_bank = bank(other, outside_gl, "FOREIGN PRIVATE BANK")
    def tx(o, when, lines, kind="JOURNAL_ENTRY"):
        t = GLTransaction(organization_id=o.id, transaction_date=when, transaction_type=kind)
        db.add(t); db.flush()
        for g, debit, credit in lines:
            db.add(GLEntry(organization_id=o.id, transaction_id=t.id,
                           gl_account_id=g.id, debit=Decimal(debit), credit=Decimal(credit)))
        db.flush()
    tx(org, date(2026, 8, 31), [(primary_gl, "100", "0")])
    tx(org, date(2026, 9, 1), [(primary_gl, "25", "0")])
    tx(org, date(2026, 9, 2), [(primary_gl, "0", "10")])
    tx(org, date(2026, 9, 3), [(primary_gl, "0", "40"), (secondary_gl, "40", "0")], "TRANSFER")
    tx(org, date(2026, 9, 4), [(secondary_gl, "0", "8")], "REVERSAL")
    tx(org, date(2026, 9, 5), [(excluded_gl, "900", "0")])
    tx(org, date(2026, 9, 5), [(unlinked_gl, "800", "0")])
    tx(other, date(2026, 9, 1), [(outside_gl, "700", "0")])
    db.add(BankFeedTransaction(
        organization_id=org.id, bank_account_id=primary.id,
        source_provider="CSV", import_key="z"*64, posted_date=date(2026, 9, 5),
        amount=Decimal("4444.00"), payee="UNPOSTED BANK FEED",
    ))
    db.commit()
    return admin, owner, manager, foreign, primary, secondary, excluded, foreign_bank


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        current_user=actor, parameters=params,
    )


def test_dated_book_cash_transfer_net_reversal_and_privacy(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, primary, secondary, excluded, foreign_bank = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        report = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        assert len(report.rows) == 3
        primary_row = next(row for row in report.rows if row[0] == primary.id)
        secondary_row = next(row for row in report.rows if row[0] == secondary.id)
        assert primary_row[3:] == (
            Decimal("100"), Decimal("25"), Decimal("50"), Decimal("-25"), Decimal("75"),
        )
        assert secondary_row[1] == "=Old Trust"
        assert secondary_row[3:] == (
            Decimal("0"), Decimal("40"), Decimal("8"), Decimal("32"), Decimal("32"),
        )
        assert report.rows[-1][3:] == (
            Decimal("100"), Decimal("65"), Decimal("58"), Decimal("7"), Decimal("107"),
        )
        csv_text = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Old Trust" in csv_text
        for secret in ("TOP-SECRET-0001", "010203040", "FOREIGN PRIVATE BANK",
                       "UNPOSTED BANK FEED", "4444.00", "900", "800"):
            assert secret not in str(report)
            assert secret not in csv_text
        assert "internal transfers inflate gross" in report.title
        assert db.query(GLEntry).count() == before
    finally:
        db.close(); engine.dispose()


def test_role_menu_dates_missing_actor_and_basis_independence(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, primary, secondary, excluded, foreign_bank = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor, date_from="2026-09-01", date_to="2026-09-30")
        for params in (
            {}, {"date_from": "2026-09-01"}, {"date_to": "2026-09-30"},
            {"date_from": "2026-09-99", "date_to": "2026-09-30"},
            {"date_from": "2026-09-30", "date_to": "2026-09-01"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30", "sql": "SELECT * FROM users"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(db, organization_id=admin.organization_id,
                                 report_key=KEY, parameters={"date_from": "2026-09-01",
                                                            "date_to": "2026-09-30"})
        monkeypatch.setattr(cash_service, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **k: True)
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        both = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        assert both.rows[-1][-1] == Decimal("107")
        assert "not a classified cash flow statement" in both.title
        foreign_read = _report(db, foreign, date_from="2026-09-01", date_to="2026-09-30")
        assert "Primary" not in str(foreign_read)
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_export_email_gate_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **k: True)
        report = next(item for item in REPORT_CATALOG if item.key == KEY)
        assert report.presentation == "TAB"
        assert report.href == "/dashboard/reporting/cash-flow"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"date_from": "2026-09-01", "date_to": "2026-09-30"})
        response = Response()
        preview = reporting_router.preview_cash_flow(req, response, db=db, current_user=admin)
        assert preview["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        assert "TOP-SECRET" not in str(preview)
        csv = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Opening Posted Book Cash" in csv.body
        assert b"TOP-SECRET" not in csv.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kw: sent.update(kw))
        outcome = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="accountant@example.com", parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert outcome.sent and b"TOP-SECRET" not in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_cash_flow(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()



def test_earliest_iso_date_has_zero_opening_and_never_underflows(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **k: True)
        result = _report(db, admin, date_from="0001-01-01", date_to="0001-01-31")
        assert result.rows[-1][3:] == (
            Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        )
    finally:
        db.close(); engine.dispose()
