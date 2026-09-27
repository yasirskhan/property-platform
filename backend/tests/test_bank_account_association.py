"""Read-only bank associations expose no bank credentials or foreign GL data."""
from __future__ import annotations

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
from app.models.user import Organization, User, UserRole
from app.services import bank_account_association as assoc
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)
from app.routers import reporting as reporting_router

KEY = "accounting.bank_association"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Bank Association One", slug="bank-association-one")
    other = Organization(name="Bank Association Other", slug="bank-association-other")
    db.add_all([first, other])
    db.flush()

    def actor(org, role, name):
        person = User(
            organization_id=org.id, role=role, first_name=name, last_name="Association",
            email=f"{name.lower()}@bank-association.example",
            hashed_password="x", is_active=True,
        )
        db.add(person)
        db.flush()
        return person

    admin = actor(first, UserRole.ADMIN, "Admin")
    owner = actor(first, UserRole.OWNER, "Owner")
    foreign = actor(other, UserRole.ADMIN, "Foreign")
    manager = actor(first, UserRole.MANAGER, "Manager")
    cash = GLAccount(
        organization_id=first.id, gl_number="1150", name="Rental Trust",
        account_type="ASSET",
    )
    noncash = GLAccount(
        organization_id=first.id, gl_number="4000", name="Income Not Cash",
        account_type="INCOME",
    )
    outside = GLAccount(
        organization_id=other.id, gl_number="9999", name="FOREIGN SECRET GL",
        account_type="ASSET",
    )
    db.add_all([cash, noncash, outside])
    db.flush()

    def bank(org, gl, name, number, **kwargs):
        b = BankAccount(
            organization_id=org.id, gl_account_id=gl.id, name=name,
            account_type="OPERATING", routing_number="001234567",
            account_number=number, **kwargs,
        )
        db.add(b); db.flush()
        return b
    current = bank(first, cash, "Primary Trust", "TOP-SECRET-012345")
    inactive = bank(first, noncash, "=Archive", "PRIVATE-2222", is_active=False)
    outside_bank = bank(other, outside, "SECRET FOREIGN BANK", "FOREIGN-PRIVATE")
    malformed = bank(first, outside, "Broken Link", "PRIVATE-3333")
    db.commit()
    return admin, owner, foreign, manager, current, inactive, outside_bank, malformed


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        current_user=actor, parameters=params,
    )


def test_scoped_mapping_only_and_no_bank_number_or_cross_org_gl(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, foreign, manager, current, inactive, foreign_bank, bad = _seed(db)
        monkeypatch.setattr(assoc, "permission_allows_user", lambda *a, **k: True)
        gl_entries = db.query(GLEntry).count()
        payload = _payload(db, admin)
        assert len(payload.rows) == 2
        mapped = next(row for row in payload.rows if row[0] == current.id)
        assert mapped[4] == "1150" and mapped[5] == "Rental Trust"
        assert mapped[7] == "MAPPED_ASSET"
        broken = next(row for row in payload.rows if row[0] == bad.id)
        assert broken[4:7] == ("", "", "")
        assert broken[7] == "UNRESOLVED"
        csv_text = report_csv_bytes(payload).decode("utf-8-sig")
        for secret in ("TOP-SECRET-012345", "001234567", "PRIVATE-2222",
                       "FOREIGN-PRIVATE", "FOREIGN SECRET GL", "SECRET FOREIGN BANK"):
            assert secret not in str(payload)
            assert secret not in csv_text
        expanded = _payload(db, admin, include_inactive="true")
        archived = next(row for row in expanded.rows if row[0] == inactive.id)
        assert archived[1] == "=Archive" and archived[3] == "INACTIVE"
        assert archived[7] == "REVIEW_NON_ASSET"
        assert "'=Archive" in report_csv_bytes(expanded).decode("utf-8-sig")
        assert db.query(GLEntry).count() == gl_entries
    finally:
        db.close(); engine.dispose()


def test_admin_menu_and_foreign_id_probes_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, foreign, manager, current, inactive, foreign_bank, bad = _seed(db)
        monkeypatch.setattr(assoc, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _payload(db, actor)
        for bank_id in (foreign_bank.id, inactive.id, 99999):
            with pytest.raises(ReportDeliveryError, match="not found"):
                _payload(db, admin, bank_id=bank_id)
        assert len(_payload(db, admin, bank_id=inactive.id, include_inactive=True).rows) == 1
        for params in ({"bank_id": "abc"}, {"bank_id": "-1"},
                       {"include_inactive": "maybe"}, {"sql": "SELECT * FROM bank_accounts"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        monkeypatch.setattr(
            assoc, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS",
        )
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(assoc, "permission_allows_user", lambda *a, **k: True)
        with pytest.raises(ReportDeliveryError, match="not found"):
            _payload(db, foreign, bank_id=current.id)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_gate_and_no_store(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, bank, *_ = _seed(db)
        monkeypatch.setattr(assoc, "permission_allows_user", lambda *a, **k: True)
        entry = next(r for r in REPORT_CATALOG if r.key == KEY)
        assert entry.presentation == "BUTTON"
        assert entry.href == "/dashboard/reporting/bank-association"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
            lambda *a, **k: [SimpleNamespace(
                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={})
        resp = Response()
        preview = reporting_router.preview_bank_account_association(
            req, resp, db=db, current_user=admin,
        )
        assert preview["total"] == 2
        assert resp.headers["cache-control"] == "no-store"
        assert "TOP-SECRET" not in str(preview)
        csv = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Bank Display Name" in csv.body and b"TOP-SECRET" not in csv.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kw: sent.update(kw))
        email = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="staff@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert email.sent
        assert b"TOP-SECRET" not in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
            lambda *a, **k: [SimpleNamespace(
                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_bank_account_association(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
