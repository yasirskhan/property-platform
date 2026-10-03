from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.settings_display as display


def test_display_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(display, "permission_allows_user", lambda *args, **kwargs: True)
    with pytest.raises(HTTPException) as exc:
        display._require_display_access(
            object(), SimpleNamespace(organization_id=None)
        )
    assert exc.value.status_code == 400


def test_display_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(display, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)

    with pytest.raises(HTTPException) as exc:
        display._require_display_access(object(), user)

    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "SETTINGS.DISPLAY"


def test_display_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(display, "permission_allows_user", lambda *args, **kwargs: True)
    assert display._require_display_access(
        object(), SimpleNamespace(organization_id=42)
    ) == 42
