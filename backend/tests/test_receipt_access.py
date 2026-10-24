from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.receipts as receipts


def test_receipts_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(receipts, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(organization_id=None)
    with pytest.raises(HTTPException) as exc:
        receipts._require_receipts_access(object(), user)
    assert exc.value.status_code == 400


def test_receipts_access_rejects_missing_receivables_permission(monkeypatch) -> None:
    seen = {}
    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False
    monkeypatch.setattr(receipts, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        receipts._require_receipts_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "ACCOUNTING.RECEIVABLES"


def test_receipts_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(receipts, "permission_allows_user", lambda *args, **kwargs: True)
    user = SimpleNamespace(organization_id=42)
    assert receipts._require_receipts_access(object(), user) == 42
