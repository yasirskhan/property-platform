from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.owner_statements as owner_statements


def test_owner_statements_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(
        owner_statements, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=None)
    with pytest.raises(HTTPException) as exc:
        owner_statements._require_owner_statements_access(object(), user)
    assert exc.value.status_code == 400


def test_owner_statements_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(owner_statements, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        owner_statements._require_owner_statements_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "ACCOUNTING.OWNER_STATEMENTS"


def test_owner_statements_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(
        owner_statements, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=42)
    assert owner_statements._require_owner_statements_access(object(), user) == 42


@pytest.mark.parametrize("role", ["ADMIN", "OWNER", "MANAGER"])
def test_owner_statement_write_roles_allow_accounting_staff(role) -> None:
    owner_statements._require_write(SimpleNamespace(role=role))


@pytest.mark.parametrize("role", ["TENANT", "CREW", "VENDOR", "APPLICANT"])
def test_owner_statement_write_roles_reject_non_accounting_users(role) -> None:
    with pytest.raises(HTTPException) as exc:
        owner_statements._require_write(SimpleNamespace(role=role))
    assert exc.value.status_code == 403
