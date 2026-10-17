from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.journal_entries as journal_entries


def test_journal_entries_access_requires_organization(monkeypatch) -> None:
    monkeypatch.setattr(
        journal_entries, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=None)
    with pytest.raises(HTTPException) as exc:
        journal_entries._require_journal_entries_access(object(), user)
    assert exc.value.status_code == 400


def test_journal_entries_access_rejects_missing_permission(monkeypatch) -> None:
    seen = {}

    def denied(_db, *, user, menu_key):
        seen["user"] = user
        seen["menu_key"] = menu_key
        return False

    monkeypatch.setattr(journal_entries, "permission_allows_user", denied)
    user = SimpleNamespace(organization_id=42)
    with pytest.raises(HTTPException) as exc:
        journal_entries._require_journal_entries_access(object(), user)
    assert exc.value.status_code == 403
    assert seen["menu_key"] == "ACCOUNTING.JOURNAL_ENTRIES"


def test_journal_entries_access_returns_org_when_permission_allows(monkeypatch) -> None:
    monkeypatch.setattr(
        journal_entries, "permission_allows_user", lambda *args, **kwargs: True
    )
    user = SimpleNamespace(organization_id=42)
    assert journal_entries._require_journal_entries_access(object(), user) == 42


@pytest.mark.parametrize("role", ["ADMIN", "OWNER", "MANAGER"])
def test_journal_entry_write_roles_allow_accounting_staff(role) -> None:
    journal_entries._require_write(SimpleNamespace(role=role))


@pytest.mark.parametrize("role", ["TENANT", "CREW", "VENDOR", "APPLICANT"])
def test_journal_entry_write_roles_reject_non_accounting_users(role) -> None:
    with pytest.raises(HTTPException) as exc:
        journal_entries._require_write(SimpleNamespace(role=role))
    assert exc.value.status_code == 403
