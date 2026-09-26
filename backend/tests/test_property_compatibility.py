from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.properties as properties


def test_property_permission_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(properties, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(role="ADMIN", organization_id=None)
    with pytest.raises(HTTPException) as exc:
        properties._require_property_permission(object(), user, "PROPERTIES.ALL")
    assert exc.value.status_code == 400


@pytest.mark.parametrize("menu_key", ["PROPERTIES.ALL", "PROPERTIES.ADD", "PROPERTIES.UNITS"])
def test_property_permission_uses_requested_menu_key(monkeypatch, menu_key) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(properties, "permission_allows_user", denied)
    user = SimpleNamespace(role="ADMIN", organization_id=42)
    with pytest.raises(HTTPException) as exc:
        properties._require_property_permission(object(), user, menu_key)
    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == menu_key


def test_property_permission_returns_org_when_allowed(monkeypatch) -> None:
    monkeypatch.setattr(properties, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(role="ADMIN", organization_id=42)
    assert properties._require_property_permission(
        object(), user, "PROPERTIES.ALL"
    ) == 42


def test_property_permission_still_blocks_tenants(monkeypatch) -> None:
    monkeypatch.setattr(properties, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(role=properties.UserRole.TENANT, organization_id=42)
    with pytest.raises(HTTPException) as exc:
        properties._require_property_permission(object(), user, "PROPERTIES.ALL")
    assert exc.value.status_code == 403
