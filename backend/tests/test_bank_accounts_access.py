from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.bank_accounts as bank_accounts


def test_bank_accounts_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(bank_accounts, "permission_allows_user", lambda *args, **kwargs: True)
    with pytest.raises(HTTPException) as exc:
        bank_accounts._require_bank_accounts_access(object(), SimpleNamespace(organization_id=None))
    assert exc.value.status_code == 400


def test_bank_accounts_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}
    def denied(_db, *, user, menu_key):
        seen["menu_key"] = menu_key
        return False
    monkeypatch.setattr(bank_accounts, "permission_allows_user", denied)
    with pytest.raises(HTTPException) as exc:
        bank_accounts._require_bank_accounts_access(object(), SimpleNamespace(organization_id=42))
    assert exc.value.status_code == 403
    assert seen["menu_key"] == "ACCOUNTING.BANK_ACCOUNTS"


def test_bank_accounts_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(bank_accounts, "permission_allows_user", lambda *args, **kwargs: True)
    assert bank_accounts._require_bank_accounts_access(object(), SimpleNamespace(organization_id=42)) == 42


@pytest.mark.parametrize("role", ["ADMIN", "OWNER", "MANAGER"])
def test_bank_account_write_roles_allow_accounting_staff(role) -> None:
    bank_accounts._require_write(SimpleNamespace(role=role))


@pytest.mark.parametrize("role", ["TENANT", "CREW", "VENDOR", "APPLICANT"])
def test_bank_account_write_roles_reject_non_accounting_users(role) -> None:
    with pytest.raises(HTTPException) as exc:
        bank_accounts._require_write(SimpleNamespace(role=role))
    assert exc.value.status_code == 403
