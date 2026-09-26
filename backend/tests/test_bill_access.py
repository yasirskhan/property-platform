from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.bills as bills


def test_bills_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(bills, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(organization_id=None)
    with pytest.raises(HTTPException) as exc:
        bills._require_bills_access(object(), user)
    assert exc.value.status_code == 400


def test_bills_access_rejects_missing_payables_permission(monkeypatch) -> None:
    seen = {}
    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False
    monkeypatch.setattr(bills, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        bills._require_bills_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "ACCOUNTING.PAYABLES"


def test_bills_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(bills, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(organization_id=42)
    assert bills._require_bills_access(object(), user) == 42


def test_bill_workflow_static_routes_do_not_collide_with_bill_id_route() -> None:
    paths = {route.path for route in bills.router.routes}
    assert "/api/accounting/bills/recurring/schedules" in paths
    assert "/api/accounting/bills/recurring/post" in paths
    assert "/api/accounting/bills/credits/list" in paths
    assert "/api/accounting/bills/recurring" not in paths
    assert "/api/accounting/bills/credits" in paths
