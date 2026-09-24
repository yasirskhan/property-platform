from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.gl_accounts as gl_accounts
from app.schemas.gl_account import GLAccountCreate, GLAccountOut, GLAccountUpdate


def test_gl_accounts_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(
        gl_accounts, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=None)
    with pytest.raises(HTTPException) as exc:
        gl_accounts._require_gl_accounts_access(object(), user)
    assert exc.value.status_code == 400


def test_gl_accounts_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(gl_accounts, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        gl_accounts._require_gl_accounts_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["menu_key"] == "ACCOUNTING.GL_ACCOUNTS"


def test_gl_accounts_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(
        gl_accounts, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=42)
    assert gl_accounts._require_gl_accounts_access(object(), user) == 42


def test_must_clear_is_part_of_gl_account_api_contract() -> None:
    created = GLAccountCreate(
        gl_number="9999",
        name="Clearing Probe",
        account_type="ASSET",
        must_clear=True,
    )
    assert created.must_clear is True
    assert GLAccountUpdate(must_clear=True).must_clear is True
    assert "must_clear" in GLAccountOut.model_fields
