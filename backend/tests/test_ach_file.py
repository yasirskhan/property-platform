from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.bank_account import BankAccount
from app.models.user import Organization
from app.schemas.ach_file import ACHEntryIn, ACHGenerateIn
from app.services.ach_file import ACHFileError, aba_valid, generate_ach_file


def bank(fmt: str = "NACHA") -> BankAccount:
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


def payload(company_id: str | None = "1234567890") -> ACHGenerateIn:
    return ACHGenerateIn(
        effective_date=date(2026, 9, 30),
        company_id=company_id,
        entry_description="OWNER PAY",
        entries=[
            ACHEntryIn(
                recipient_name="Owner One",
                routing_number="021000021",
                account_number="99887766",
                account_type="CHECKING",
                amount=Decimal("125.50"),
                identification="OWNER-1",
            ),
            ACHEntryIn(
                recipient_name="Owner Two",
                routing_number="011000015",
                account_number="11223344",
                account_type="SAVINGS",
                amount=Decimal("74.50"),
            ),
        ],
    )


@pytest.mark.accounting
def test_nacha_generation_has_94_char_records_controls_and_no_state_mutation():
    org = Organization(id=1, name="Example Property Management", slug="example")
    b = bank()
    filename, content_type, content, total = generate_ach_file(
        bank=b,
        organization=org,
        payload=payload(),
        now=datetime(2026, 9, 24, 12, 34),
    )
    rows = content.splitlines()
    assert filename == "ach-client-trust-20260930.ach"
    assert content_type == "text/plain"
    assert total == Decimal("200.00")
    assert len(rows) == 10
    assert all(len(row) == 94 for row in rows)
    assert rows[0].startswith("101 021000021 0210000212609241234A094101")
    assert rows[1].startswith("5220")
    assert rows[2].startswith("622021000021")
    assert rows[3].startswith("632011000015")
    assert rows[4].startswith("8220000002")
    assert rows[5].startswith("900000100000100000002")
    assert b.ach_format == "NACHA"


@pytest.mark.accounting
def test_csv_generation_and_routing_validation():
    org = Organization(id=1, name="Example", slug="example")
    b = bank("CSV")
    filename, content_type, content, total = generate_ach_file(
        bank=b,
        organization=org,
        payload=payload(company_id=None),
    )
    assert filename.endswith(".csv")
    assert content_type == "text/csv"
    assert "recipient_name,routing_number,account_number" in content
    assert "Owner One,021000021,99887766,CHECKING,125.50,OWNER-1" in content
    assert total == Decimal("200.00")
    assert aba_valid("021000021")
    assert not aba_valid("021000022")


@pytest.mark.accounting
def test_nacha_requires_company_id_and_valid_source_bank():
    org = Organization(id=1, name="Example", slug="example")
    with pytest.raises(ACHFileError, match="company_id"):
        generate_ach_file(bank=bank(), organization=org, payload=payload(company_id=None))
    bad = bank()
    bad.routing_number = "123456789"
    with pytest.raises(ACHFileError, match="Source bank routing"):
        generate_ach_file(bank=bad, organization=org, payload=payload())
