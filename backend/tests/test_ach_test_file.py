from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.bank_account import BankAccount
from app.models.owner_ach import OwnerACHAccount
from app.models.user import Organization
from app.services.ach_file import ACHFileError, generate_ach_test_file


def source_bank(fmt: str) -> BankAccount:
    return BankAccount(
        id=1,
        organization_id=1,
        name="Client Trust",
        bank_name="Test Bank",
        routing_number="021000021",
        account_number="123456789",
        gl_account_id=1,
        account_type="OPERATING",
        ach_format=fmt,
        is_active=True,
    )


def destination(account_type: str = "CHECKING") -> OwnerACHAccount:
    return OwnerACHAccount(
        id=1,
        organization_id=1,
        owner_id=7,
        account_holder_name="Owner One",
        bank_name="Owner Bank",
        routing_number="021000021",
        account_number="987654321",
        account_type=account_type,
        is_enabled=True,
    )


@pytest.mark.accounting
def test_csv_ach_test_file_is_zero_dollar_and_non_posting_payload() -> None:
    filename, content_type, content = generate_ach_test_file(
        bank=source_bank("CSV"),
        organization=Organization(id=1, name="Test Org", slug="test-org"),
        owner_ach=destination(),
        effective_date=date(2026, 9, 25),
        company_id=None,
    )

    assert filename == "ach-test-client-trust-20260925.csv"
    assert content_type == "text/csv"
    assert "0.00" in content
    assert "PRENOTE" in content
    assert "Owner One" in content
    assert "987654321" in content


@pytest.mark.accounting
def test_nacha_ach_test_file_uses_prenote_transaction_code_and_zero_amount() -> None:
    filename, content_type, content = generate_ach_test_file(
        bank=source_bank("NACHA"),
        organization=Organization(id=1, name="Test Org", slug="test-org"),
        owner_ach=destination("CHECKING"),
        effective_date=date(2026, 9, 25),
        company_id="1234567890",
        now=datetime(2026, 9, 25, 9, 30),
    )

    rows = content.splitlines()
    entry = next(row for row in rows if row.startswith("6"))
    assert filename == "ach-test-client-trust-20260925.ach"
    assert content_type == "text/plain"
    assert all(len(row) == 94 for row in rows)
    assert entry.startswith("623")
    assert entry[29:39] == "0000000000"


@pytest.mark.accounting
def test_nacha_ach_test_file_requires_company_id_and_valid_destination() -> None:
    with pytest.raises(ACHFileError, match="company_id"):
        generate_ach_test_file(
            bank=source_bank("NACHA"),
            organization=Organization(id=1, name="Test Org", slug="test-org"),
            owner_ach=destination(),
            effective_date=date(2026, 9, 25),
            company_id=None,
        )

    bad = destination()
    bad.routing_number = "123456789"
    with pytest.raises(ACHFileError, match="Owner routing"):
        generate_ach_test_file(
            bank=source_bank("CSV"),
            organization=Organization(id=1, name="Test Org", slug="test-org"),
            owner_ach=bad,
            effective_date=date(2026, 9, 25),
            company_id=None,
        )
