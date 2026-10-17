"""Twelve-month cash-book report preserves verified monthly GL semantics."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.models.gl_entry import GLEntry
from app.models.user import UserRole
from app.routers import reporting as reporting_router
from app.services import cash_flow as cash_service
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)
from test_cash_flow import _session, _seed

KEY = "accounting.cash_flow_12_month"


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        current_user=actor, parameters=params,
    )


def test_twelve_calendar_months_year_rollover_transfer_and_reversal(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, primary, secondary, excluded, foreign_bank = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **kw: True)
        previous = db.query(GLEntry).count()
        result = _report(db, admin, ending_month="2026-09")
        assert len(result.rows) == 13
        assert result.rows[0][0] == "2025-10"
        assert result.rows[-2][0] == "2026-09"
        assert result.rows[0][1:] == (Decimal("0"),)*5
        assert result.rows[-2][1:] == (
            Decimal("100"), Decimal("65"), Decimal("58"), Decimal("7"), Decimal("107"),
        )
        assert result.rows[-1][1:] == (
            Decimal("0"), Decimal("165"), Decimal("58"), Decimal("107"), Decimal("107"),
        )
        assert "internal transfers inflate gross" in result.title
        data = report_csv_bytes(result).decode("utf-8-sig")
        for secret in ("TOP-SECRET-0001", "010203040",
                       "FOREIGN PRIVATE BANK", "UNPOSTED BANK FEED", "4444.00"):
            assert secret not in str(result)
            assert secret not in data
        assert db.query(GLEntry).count() == previous
    finally:
        db.close(); engine.dispose()


def test_year_one_edge_invalid_dates_and_permission_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, owner, manager, foreign, *_ = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **kw: True)
        earliest = _report(db, admin, ending_month="0001-12")
        assert earliest.rows[0][0] == "0001-01"
        assert earliest.rows[-1][-1] == Decimal("0")
        for params in (
            {}, {"ending_month": "2026"}, {"ending_month": "2026-00"},
            {"ending_month": "2026-13"}, {"ending_month": "0001-11"},
            {"ending_month": "0000-12"}, {"ending_month": "2026-9"},
            {"ending_month": "2026-12", "sql": "SELECT * FROM users"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        for actor in (owner, manager):
            with pytest.raises(ReportDeliveryError, match="permission"):
                _report(db, actor, ending_month="2026-09")
        foreign_result = _report(db, foreign, ending_month="2026-09")
        assert "Primary" not in str(foreign_result)
        monkeypatch.setattr(cash_service, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin, ending_month="2026-09")
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(cash_service, "permission_allows_user", lambda *a, **kw: True)
        record = next(item for item in REPORT_CATALOG if item.key == KEY)
        assert record.presentation == "TAB"
        assert record.href == "/dashboard/reporting/cash-flow-12-month"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"ending_month": "2026-09"})
        response = Response()
        preview = reporting_router.preview_cash_flow_12_month(
            req, response, db=db, current_user=admin,
        )
        assert preview["total"] == 13
        assert response.headers["cache-control"] == "no-store"
        assert "TOP-SECRET" not in str(preview)
        exported = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"TOTAL 12 MONTHS" in exported.body
        assert b"TOP-SECRET" not in exported.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kwargs: sent.update(kwargs))
        done = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="accountant@example.com", parameters=dict(req.query_params)),
            db=db, current_user=admin,
        )
        assert done.sent and b"TOP-SECRET" not in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_cash_flow_12_month(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
