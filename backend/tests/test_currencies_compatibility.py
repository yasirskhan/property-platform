from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.currencies as currencies


def test_currency_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(currencies, "permission_allows_user", lambda *args, **kwargs: True)
    with pytest.raises(HTTPException) as exc:
        currencies._require_currency_access(
            object(), SimpleNamespace(organization_id=None)
        )
    assert exc.value.status_code == 400


def test_currency_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(currencies, "_get_org", lambda _db, _user: object())
    monkeypatch.setattr(currencies, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)

    with pytest.raises(HTTPException) as exc:
        currencies._require_currency_access(object(), user)

    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "SETTINGS.CURRENCIES"


def test_currency_access_returns_org_when_permission_allows(monkeypatch) -> None:
    org = object()
    monkeypatch.setattr(currencies, "_get_org", lambda _db, _user: org)
    monkeypatch.setattr(currencies, "permission_allows_user", lambda *args, **kwargs: True)

    assert currencies._require_currency_access(
        object(), SimpleNamespace(organization_id=42)
    ) is org


@pytest.mark.parametrize("role", ["ADMIN", "OWNER"])
def test_currency_write_roles_allow_admin_and_owner(role) -> None:
    currencies._require_writer(SimpleNamespace(role=role))


@pytest.mark.parametrize("role", ["MANAGER", "CREW", "TENANT", "VENDOR", "APPLICANT"])
def test_currency_write_roles_reject_other_roles(role) -> None:
    with pytest.raises(HTTPException) as exc:
        currencies._require_writer(SimpleNamespace(role=role))
    assert exc.value.status_code == 403
