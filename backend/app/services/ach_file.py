"""Stateless CSV/NACHA credit-file generation for configured bank accounts."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.models.bank_account import BankAccount
from app.models.owner_ach import OwnerACHAccount
from app.models.user import Organization
from app.schemas.ach_file import ACHGenerateIn

CENT = Decimal("0.01")


class ACHFileError(ValueError):
    pass


def _money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def aba_valid(routing: str) -> bool:
    if len(routing) != 9 or not routing.isdigit():
        return False
    digits = [int(x) for x in routing]
    return (
        3 * (digits[0] + digits[3] + digits[6])
        + 7 * (digits[1] + digits[4] + digits[7])
        + (digits[2] + digits[5] + digits[8])
    ) % 10 == 0


def _ascii(value: str | None, width: int) -> str:
    raw = (value or "").upper().encode("ascii", "ignore").decode("ascii")
    clean = "".join(ch for ch in raw if ch.isalnum() or ch in " .&-")
    return clean[:width].ljust(width)


def _digits_account(value: str | None) -> str:
    raw = (value or "").strip().replace(" ", "").replace("-", "")
    if not raw or not raw.isalnum() or len(raw) > 17:
        raise ACHFileError("Source bank account number is required and must be 17 characters or fewer.")
    return raw


def _validate(bank: BankAccount, payload: ACHGenerateIn) -> tuple[str, str]:
    fmt = (bank.ach_format or "").upper()
    if fmt not in {"CSV", "NACHA"}:
        raise ACHFileError("Bank account ACH format must be configured as CSV or NACHA.")
    routing = (bank.routing_number or "").strip()
    if not aba_valid(routing):
        raise ACHFileError("Source bank routing number must be a valid 9-digit ABA routing number.")
    _digits_account(bank.account_number)
    for entry in payload.entries:
        if not aba_valid(entry.routing_number):
            raise ACHFileError(f"Recipient {entry.recipient_name} has an invalid ABA routing number.")
        if _money(entry.amount) <= 0:
            raise ACHFileError("ACH amounts must be greater than zero.")
    if fmt == "NACHA" and not (payload.company_id or "").strip():
        raise ACHFileError("company_id is required for NACHA generation.")
    return fmt, routing


def _csv_file(bank: BankAccount, payload: ACHGenerateIn) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([
        "effective_date",
        "recipient_name",
        "routing_number",
        "account_number",
        "account_type",
        "amount",
        "identification",
    ])
    for entry in payload.entries:
        writer.writerow([
            payload.effective_date.isoformat(),
            entry.recipient_name,
            entry.routing_number,
            entry.account_number,
            entry.account_type,
            f"{_money(entry.amount):.2f}",
            entry.identification or "",
        ])
    return output.getvalue()


def _nacha_file(bank: BankAccount, organization: Organization, payload: ACHGenerateIn, now: datetime) -> str:
    routing = (bank.routing_number or "").strip()
    odfi = routing[:8]
    company_id = (payload.company_id or "").strip()[:10].ljust(10)
    batch_no = 1
    effective = payload.effective_date.strftime("%y%m%d")
    creation_date = now.strftime("%y%m%d")
    creation_time = now.strftime("%H%M")

    records: list[str] = []
    file_header = (
        "1" + "01" + f" {routing}" + f" {routing}" + creation_date + creation_time
        + "A" + "094" + "10" + "1"
        + _ascii(bank.bank_name or bank.name, 23)
        + _ascii(organization.name, 23)
        + " " * 8
    )
    records.append(file_header)

    batch_header = (
        "5" + "220" + _ascii(organization.name, 16) + " " * 20 + company_id
        + "PPD" + _ascii(payload.entry_description, 10) + " " * 6 + effective
        + " " * 3 + "1" + odfi + f"{batch_no:07d}"
    )
    records.append(batch_header)

    entry_hash = 0
    total_credit_cents = 0
    for index, entry in enumerate(payload.entries, start=1):
        cents = int((_money(entry.amount) * 100).to_integral_value())
        total_credit_cents += cents
        entry_hash += int(entry.routing_number[:8])
        transaction_code = "22" if entry.account_type == "CHECKING" else "32"
        trace = odfi + f"{index:07d}"
        record = (
            "6" + transaction_code + entry.routing_number[:8] + entry.routing_number[8]
            + entry.account_number[:17].ljust(17)
            + f"{cents:010d}"
            + _ascii(entry.identification, 15)
            + _ascii(entry.recipient_name, 22)
            + " " * 2 + "0" + trace
        )
        records.append(record)

    entry_count = len(payload.entries)
    hash_value = entry_hash % 10_000_000_000
    batch_control = (
        "8" + "220" + f"{entry_count:06d}" + f"{hash_value:010d}"
        + f"{0:012d}" + f"{total_credit_cents:012d}" + company_id
        + " " * 19 + " " * 6 + odfi + f"{batch_no:07d}"
    )
    records.append(batch_control)

    pre_control_count = len(records) + 1
    block_count = (pre_control_count + 9) // 10
    file_control = (
        "9" + f"{1:06d}" + f"{block_count:06d}" + f"{entry_count:08d}"
        + f"{hash_value:010d}" + f"{0:012d}" + f"{total_credit_cents:012d}" + " " * 39
    )
    records.append(file_control)
    while len(records) % 10:
        records.append("9" * 94)

    if any(len(row) != 94 for row in records):
        raise ACHFileError("Generated NACHA record length validation failed.")
    return "\r\n".join(records) + "\r\n"


def generate_ach_file(
    *,
    bank: BankAccount,
    organization: Organization,
    payload: ACHGenerateIn,
    now: datetime | None = None,
) -> tuple[str, str, str, Decimal]:
    fmt, _routing = _validate(bank, payload)
    total = sum((_money(entry.amount) for entry in payload.entries), Decimal("0.00"))
    stamp = payload.effective_date.strftime("%Y%m%d")
    safe_name = "".join(ch.lower() if ch.isalnum() else "-" for ch in bank.name).strip("-") or "bank"
    if fmt == "CSV":
        content = _csv_file(bank, payload)
        return f"ach-{safe_name}-{stamp}.csv", "text/csv", content, _money(total)
    content = _nacha_file(bank, organization, payload, now or datetime.utcnow())
    return f"ach-{safe_name}-{stamp}.ach", "text/plain", content, _money(total)


def _validate_test_destination(
    bank: BankAccount,
    owner_ach: OwnerACHAccount,
    *,
    company_id: str | None,
) -> str:
    fmt = (bank.ach_format or "").upper()
    if fmt not in {"CSV", "NACHA"}:
        raise ACHFileError("Bank account ACH format must be configured as CSV or NACHA.")
    source_routing = (bank.routing_number or "").strip()
    if not aba_valid(source_routing):
        raise ACHFileError("Source bank routing number must be a valid 9-digit ABA routing number.")
    _digits_account(bank.account_number)

    destination_routing = (owner_ach.routing_number or "").strip()
    if not aba_valid(destination_routing):
        raise ACHFileError("Owner routing number must be a valid 9-digit ABA routing number.")
    destination_account = (owner_ach.account_number or "").strip().replace(" ", "").replace("-", "")
    if not destination_account or not destination_account.isalnum():
        raise ACHFileError("Owner account number is not configured correctly.")
    if fmt == "NACHA" and len(destination_account) > 17:
        raise ACHFileError("Owner account number must be 17 characters or fewer for NACHA.")
    if fmt == "NACHA" and not (company_id or "").strip():
        raise ACHFileError("company_id is required for NACHA test-file generation.")
    return fmt


def _csv_test_file(
    owner_ach: OwnerACHAccount,
    *,
    effective_date: date,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([
        "effective_date",
        "recipient_name",
        "routing_number",
        "account_number",
        "account_type",
        "amount",
        "purpose",
    ])
    writer.writerow([
        effective_date.isoformat(),
        owner_ach.account_holder_name,
        owner_ach.routing_number,
        owner_ach.account_number,
        owner_ach.account_type,
        "0.00",
        "PRENOTE",
    ])
    return output.getvalue()


def _nacha_test_file(
    bank: BankAccount,
    organization: Organization,
    owner_ach: OwnerACHAccount,
    *,
    effective_date: date,
    company_id: str,
    entry_description: str,
    now: datetime,
) -> str:
    routing = (bank.routing_number or "").strip()
    odfi = routing[:8]
    company = company_id.strip()[:10].ljust(10)
    effective = effective_date.strftime("%y%m%d")
    creation_date = now.strftime("%y%m%d")
    creation_time = now.strftime("%H%M")
    batch_no = 1

    records: list[str] = []
    records.append(
        "1" + "01" + f" {routing}" + f" {routing}" + creation_date + creation_time
        + "A" + "094" + "10" + "1"
        + _ascii(bank.bank_name or bank.name, 23)
        + _ascii(organization.name, 23)
        + " " * 8
    )
    records.append(
        "5" + "220" + _ascii(organization.name, 16) + " " * 20 + company
        + "PPD" + _ascii(entry_description or "PRENOTE", 10) + " " * 6 + effective
        + " " * 3 + "1" + odfi + f"{batch_no:07d}"
    )

    destination_routing = owner_ach.routing_number.strip()
    destination_account = owner_ach.account_number.strip().replace(" ", "").replace("-", "")
    transaction_code = "23" if owner_ach.account_type == "CHECKING" else "33"
    trace = odfi + "0000001"
    records.append(
        "6" + transaction_code
        + destination_routing[:8] + destination_routing[8]
        + destination_account[:17].ljust(17)
        + "0000000000"
        + _ascii(f"TEST{owner_ach.owner_id}", 15)
        + _ascii(owner_ach.account_holder_name, 22)
        + " " * 2 + "0" + trace
    )

    entry_hash = int(destination_routing[:8]) % 10_000_000_000
    records.append(
        "8" + "220" + "000001" + f"{entry_hash:010d}"
        + "000000000000" + "000000000000" + company
        + " " * 19 + " " * 6 + odfi + f"{batch_no:07d}"
    )

    pre_control_count = len(records) + 1
    block_count = (pre_control_count + 9) // 10
    records.append(
        "9" + "000001" + f"{block_count:06d}" + "00000001"
        + f"{entry_hash:010d}" + "000000000000" + "000000000000" + " " * 39
    )
    while len(records) % 10:
        records.append("9" * 94)

    if any(len(row) != 94 for row in records):
        raise ACHFileError("Generated NACHA test-file record length validation failed.")
    return "\r\n".join(records) + "\r\n"


def generate_ach_test_file(
    *,
    bank: BankAccount,
    organization: Organization,
    owner_ach: OwnerACHAccount,
    effective_date: date,
    company_id: str | None,
    entry_description: str = "PRENOTE",
    now: datetime | None = None,
) -> tuple[str, str, str]:
    fmt = _validate_test_destination(
        bank,
        owner_ach,
        company_id=company_id,
    )
    stamp = effective_date.strftime("%Y%m%d")
    safe_name = "".join(
        ch.lower() if ch.isalnum() else "-" for ch in bank.name
    ).strip("-") or "bank"

    if fmt == "CSV":
        return (
            f"ach-test-{safe_name}-{stamp}.csv",
            "text/csv",
            _csv_test_file(owner_ach, effective_date=effective_date),
        )

    return (
        f"ach-test-{safe_name}-{stamp}.ach",
        "text/plain",
        _nacha_test_file(
            bank,
            organization,
            owner_ach,
            effective_date=effective_date,
            company_id=(company_id or ""),
            entry_description=entry_description,
            now=now or datetime.utcnow(),
        ),
    )
