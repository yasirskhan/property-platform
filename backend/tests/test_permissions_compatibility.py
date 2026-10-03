from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.menu_permissions as permissions


def test_permissions_management_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(permissions, "permission_allows_user", lambda *args, **kwargs: True)
    with pytest.raises(HTTPException) as exc:
        permissions._require_permissions_management(
            object(), SimpleNamespace(organization_id=None)
        )
    assert exc.value.status_code == 400


def test_permissions_management_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(permissions, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)

    with pytest.raises(HTTPException) as exc:
        permissions._require_permissions_management(object(), user)

    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "SETTINGS.PERMISSIONS"


def test_permissions_management_returns_org_when_allowed(monkeypatch) -> None:
    monkeypatch.setattr(permissions, "permission_allows_user", lambda *args, **kwargs: True)
    assert permissions._require_permissions_management(
        object(), SimpleNamespace(organization_id=42)
    ) == 42


def test_my_preferences_contract_does_not_require_privileged_helper(monkeypatch) -> None:
    class Query:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class DB:
        def query(self, *args, **kwargs):
            return Query()

    def should_not_run(*args, **kwargs):
        raise AssertionError("privileged permissions helper must not gate My Preferences")

    monkeypatch.setattr(permissions, "_require_permissions_management", should_not_run)
    out = permissions.get_my_preferences(
        db=DB(),
        current_user=SimpleNamespace(id=7, organization_id=42),
    )
    assert out.order == []
    assert out.hidden == []
