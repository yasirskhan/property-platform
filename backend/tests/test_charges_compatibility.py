from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.charges as charges


def test_charges_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(charges, "permission_allows_user", lambda *args, **kwargs: True)
    with pytest.raises(HTTPException) as exc:
        charges._require_charges_access(object(), SimpleNamespace(organization_id=None))
    assert exc.value.status_code == 400


def test_charges_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(charges, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        charges._require_charges_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["user"] is user
    assert seen["menu_key"] == "ACCOUNTING.CHARGES"


def test_charges_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(charges, "permission_allows_user", lambda *args, **kwargs: True)
    assert charges._require_charges_access(
        object(), SimpleNamespace(organization_id=42)
    ) == 42


@pytest.mark.parametrize("role", ["ADMIN", "OWNER", "MANAGER"])
def test_charge_write_roles_allow_accounting_staff(role) -> None:
    charges._require_write(SimpleNamespace(role=role))


@pytest.mark.parametrize("role", ["TENANT", "CREW", "VENDOR", "APPLICANT"])
def test_charge_write_roles_reject_non_accounting_users(role) -> None:
    with pytest.raises(HTTPException) as exc:
        charges._require_write(SimpleNamespace(role=role))
    assert exc.value.status_code == 403
