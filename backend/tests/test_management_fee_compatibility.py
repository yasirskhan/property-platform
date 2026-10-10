from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.management_fees as management_fees


def test_management_fees_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(
        management_fees, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=None)
    with pytest.raises(HTTPException) as exc:
        management_fees._require_management_fees_access(object(), user)
    assert exc.value.status_code == 400


def test_management_fees_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(management_fees, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        management_fees._require_management_fees_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "ACCOUNTING.MANAGEMENT_FEES"


def test_management_fees_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(
        management_fees, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=42)
    assert management_fees._require_management_fees_access(object(), user) == 42


@pytest.mark.parametrize("role", ["ADMIN", "OWNER", "MANAGER"])
def test_management_fee_write_roles_allow_accounting_staff(role) -> None:
    management_fees._require_write(SimpleNamespace(role=role))


@pytest.mark.parametrize("role", ["TENANT", "CREW", "VENDOR", "APPLICANT"])
def test_management_fee_write_roles_reject_non_accounting_users(role) -> None:
    with pytest.raises(HTTPException) as exc:
        management_fees._require_write(SimpleNamespace(role=role))
    assert exc.value.status_code == 403
