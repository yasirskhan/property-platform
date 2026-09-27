"""Posted Journal Entry Register: original journals and only their linked reversals."""
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
from app.services import journal_entry_register as register
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as router

KEY = "transaction.journal_entry_register"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    own = Organization(name="Journal Register Org", slug="journal-register-org")
    other = Organization(name="Foreign Journal Org", slug="foreign-journal-org")
    db.add_all([own, other])
    db.flush()

    def user(org, role, name):
        result = User(organization_id=org.id, role=role, first_name=name,
                      last_name="Journal", email=f"{name.lower()}@journal-register.example",
                      hashed_password="x", is_active=True)
        db.add(result)
        db.flush()
        return result

    admin = user(own, UserRole.ADMIN, "LocalAdmin")
    manager = user(own, UserRole.MANAGER, "LocalManager")
    foreign = user(other, UserRole.ADMIN, "ForeignAdmin")

    def gl(org, number, kind, active=True):
        row = GLAccount(organization_id=org.id, gl_number=number,
                        name=f"=Journal {number}", account_type=kind, is_active=active)
        db.add(row)
        db.flush()
        return row

    cash = gl(own, "1000", "ASSET")
    income = gl(own, "4100", "INCOME", active=False)
    foreign_cash = gl(other, "1000", "ASSET")
    foreign_income = gl(other, "4100", "INCOME")

    def txn(org, when, kind, dr, cr, *, reversed=False, reversal_of=None, ref="=JE"):
        t = GLTransaction(
            organization_id=org.id, transaction_date=when,
            transaction_type=kind, reference_number=ref,
            source_type="manual_je" if kind == "JOURNAL_ENTRY" else "reversal",
            is_reversed=reversed, reversal_of_id=reversal_of,
        )
        db.add(t)
        db.flush()
        for account, debit, credit in ((dr, "100", "0"), (cr, "0", "100")):
            db.add(GLEntry(organization_id=org.id, transaction_id=t.id,
                           gl_account_id=account.id, description="=Line",
                           debit=Decimal(debit), credit=Decimal(credit)))
        db.flush()
        return t

    original = txn(own, date(2026, 9, 1), "JOURNAL_ENTRY", cash, income, reversed=True)
    reversal = txn(own, date(2026, 9, 2), "REVERSAL", income, cash,
                   reversal_of=original.id, ref="=REV")
    txn(own, date(2026, 9, 3), "BILL", cash, income, ref="OTHER")
    bill_reversal = txn(own, date(2026, 9, 4), "REVERSAL", income, cash,
                        ref="OTHER-REV")
    bill_reversal.reversal_of_id = db.query(GLTransaction).filter(
        GLTransaction.reference_number == "OTHER",
        GLTransaction.organization_id == own.id,
    ).one().id
    txn(own, date(2026, 8, 31), "JOURNAL_ENTRY", cash, income, ref="OLD")
    txn(other, date(2026, 9, 1), "JOURNAL_ENTRY", foreign_cash, foreign_income, ref="FOREIGN")
    db.commit()
    return admin, manager, foreign, original, reversal, cash, income, foreign_cash


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=params,
    )


def test_actual_journal_and_reversal_only_balanced_org_scoped_csv(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, original, reversal, cash, income, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        count = db.query(GLEntry).count()
        p = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        assert len(p.rows) == 5
        assert [row[1] for row in p.rows[:-1]] == [
            original.id, original.id, reversal.id, reversal.id,
        ]
        assert p.rows[0][5] == "REVERSED"
        assert p.rows[2][5] == f"REVERSAL OF {original.id}"
        assert p.rows[-1][-2:] == (Decimal("200"), Decimal("200"))
        assert "CASH/ACCRUAL" in p.title
        first = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30",
                        include_reversals=False)
        assert len(first.rows) == 3
        only = _report(db, admin, date_from="2026-09-01", date_to="2026-09-30",
                       transaction_id=original.id)
        assert len(only.rows) == 3
        csv = report_csv_bytes(p).decode("utf-8-sig")
        assert "'=Journal 1000" in csv and "'=JE" in csv and "'=Line" in csv
        assert "FOREIGN" not in csv and "OTHER" not in csv and "OLD" not in csv
        assert db.query(GLEntry).count() == count
    finally:
        db.close()
        engine.dispose()


def test_role_filters_balance_and_org_integrity_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, original, reversal, cash, income, foreign_cash = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        for params in (
            {},
            {"date_from": "2026-09-01"},
            {"date_from": "2026-10-01", "date_to": "2026-09-01"},
            {"date_from": "bad", "date_to": "2026-09-30"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30", "sql": "DROP TABLE"},
            {"date_from": "2026-09-01", "date_to": "2026-09-30",
             "transaction_id": 999999},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, manager, date_from="2026-09-01", date_to="2026-09-30")
        with pytest.raises(ReportDeliveryError, match="not found"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30",
                    transaction_id=db.query(GLTransaction).filter_by(
                        organization_id=foreign.organization_id,
                        reference_number="FOREIGN",
                    ).one().id)
        monkeypatch.setattr(register, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.JOURNAL_ENTRIES")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        # Posted journals are immutable book entries even if display basis changes.
        db.add(AccountingSettings(organization_id=admin.organization_id,
                                  accounting_basis="CASH"))
        db.commit()
        assert _report(db, admin, date_from="2026-09-01",
                       date_to="2026-09-30").rows[-1][-2:] == (
                           Decimal("200"), Decimal("200"))
        # Corrupt cross-org GL link must be rejected, not shown to admin.
        target = db.query(GLEntry).filter_by(transaction_id=original.id).first()
        target.gl_account_id = foreign_cash.id
        db.commit()
        with pytest.raises(ReportDeliveryError, match="organization"):
            _report(db, admin, date_from="2026-09-01", date_to="2026-09-30")
    finally:
        db.close()
        engine.dispose()


def test_catalog_preview_csv_email_gates_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(register, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.href == "/dashboard/reporting/journal-entry-register"
        assert item.presentation == "BUTTON"
        assert router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.JOURNAL_ENTRIES"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"date_from": "2026-09-01", "date_to": "2026-09-30"})
        res = Response()
        preview = router.preview_journal_entry_register(req, res, db=db, current_user=admin)
        assert preview["total"] == 5 and res.headers["cache-control"] == "no-store"
        export = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Original Journal ID" in export.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        result = router.email_report(
            KEY, router.ReportEmailIn(recipient="finance@example.com",
                                      parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert result.sent and b"FOREIGN" not in sent["attachments"][0][1]
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            router.preview_journal_entry_register(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
