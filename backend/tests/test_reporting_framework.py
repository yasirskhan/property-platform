from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.reporting as reporting_router
from app.services.report_catalog import REPORT_CATALOG, report_catalog


def test_report_catalog_has_stable_unique_keys_and_tiers():
    keys = [item.key for item in REPORT_CATALOG]
    assert len(keys) == len(set(keys))
    standard, enhanced = report_catalog()
    assert standard
    assert enhanced
    assert all(item.tier == "STANDARD" and item.presentation == "BUTTON" for item in standard)
    assert all(item.tier == "ENHANCED" and item.presentation == "TAB" for item in enhanced)


def test_existing_reports_are_wired_into_framework():
    by_key = {item.key: item for item in REPORT_CATALOG}
    assert by_key["accounting.trial_balance"].available is True
    assert by_key["accounting.trial_balance"].href == "/dashboard/accounting/trial-balance"
    assert by_key["accounting.general_ledger"].available is True
    assert by_key["accounting.chart_of_accounts"].available is True
    assert by_key["owner.statement"].available is True


def test_reporting_catalog_requires_menu_permission(monkeypatch):
    user = SimpleNamespace(organization_id=42)
    monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: False)
    with pytest.raises(HTTPException) as exc:
        reporting_router.get_report_catalog(db=object(), current_user=user)
    assert exc.value.status_code == 403


def test_reporting_catalog_returns_org_accounting_basis(monkeypatch):
    user = SimpleNamespace(organization_id=42)
    monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(
        reporting_router,
        "get_accounting_basis",
        lambda db, *, organization_id: "CASH" if organization_id == 42 else "ACCRUAL",
    )
    result = reporting_router.get_report_catalog(db=object(), current_user=user)
    assert result.accounting_basis == "CASH"
    assert len(result.standard) + len(result.enhanced) == len(REPORT_CATALOG)
