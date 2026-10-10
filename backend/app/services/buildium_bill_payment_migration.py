"""Buildium bill-payment relationship reconciliation for Phase 4.14.

This bounded adapter handles only the subset that can be proven against the
target Check + Bill + immutable GL contracts: one fully-paid bill, a durable
check number, no vendor credits, and exact mapped line relationships.

It never creates or updates a Check, Bill, payment, GL transaction, bank
movement, vendor credit, or provider credential. Partial, multi-bill,
non-check, and vendor-credit payments remain explicitly unsupported.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.check import Check, CheckBillAllocation
from app.models.gl_account import GLAccount
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit


class BuildiumBillPaymentMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class BillPaymentDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class BillPaymentCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return str(number) if number > 0 else None


def _money(value: Any, *, field: str) -> tuple[Decimal | None, str | None]:
    if isinstance(value, bool):
        return None, f"{field} must be a positive two-decimal amount."
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field} must be a positive two-decimal amount."
    if not amount.is_finite() or amount <= 0:
        return None, f"{field} must be a positive finite amount."
    rounded = amount.quantize(Decimal("0.01"))
    if amount != rounded:
        return None, f"{field} cannot contain more than two decimal places."
    return rounded, None


def _date(value: Any, *, field: str) -> tuple[date | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, f"{field} is required."
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, f"{field} must be an ISO date (YYYY-MM-DD)."


def _mapping(
    db: Session,
    *,
    run: PlatformMigrationRun,
    resource: str,
    source_id: str,
    target_entity: str,
) -> PlatformMigrationItem | None:
    row = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == resource,
            PlatformMigrationItem.source_id == source_id,
        )
        .first()
    )
    if row is not None and row.target_entity != target_entity:
        raise BuildiumBillPaymentMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumBillPaymentMigrationError(
                "Bill Payment review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumBillPaymentMigrationError(
                f"Duplicate Bill Payment review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBillPaymentMigrationError(
                "Bill Payment review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_check_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumBillPaymentMigrationError(
                    "MATCH_EXISTING requires a positive target Check ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumBillPaymentMigrationError(
                    "MATCH_EXISTING requires a positive target Check ID."
                )
            if target < 1:
                raise BuildiumBillPaymentMigrationError(
                    "MATCH_EXISTING requires a positive target Check ID."
                )
        elif target is not None:
            raise BuildiumBillPaymentMigrationError(
                "target_check_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_check_id": target,
        }
    return result


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for record in records:
        bank_source_id = _positive_id(record.get("BankAccountId"))
        bill_ids = record.get("PaidBillIds")
        bill_source_ids = (
            [_positive_id(value) for value in bill_ids]
            if isinstance(bill_ids, list)
            else []
        )
        line_dependencies: list[dict[str, Any]] = []
        lines = record.get("Lines")
        if isinstance(lines, list):
            for line in lines:
                entity = line.get("AccountingEntity") if isinstance(line, dict) else None
                property_source_id = (
                    _positive_id(entity.get("Id")) if isinstance(entity, dict) else None
                )
                unit_source_id = (
                    _positive_id(entity.get("UnitId")) if isinstance(entity, dict) else None
                )
                gl_source_id = (
                    _positive_id(line.get("GLAccountId"))
                    if isinstance(line, dict)
                    else None
                )
                deps: dict[str, Any] = {
                    "property_source_id": property_source_id,
                    "unit_source_id": unit_source_id,
                    "gl_account_source_id": gl_source_id,
                }
                for key, resource, source_id, target_entity in (
                    ("property", "PROPERTIES", property_source_id, "PROPERTY"),
                    ("unit", "UNITS", unit_source_id, "UNIT"),
                    ("gl_account", "GL_ACCOUNTS", gl_source_id, "GL_ACCOUNT"),
                ):
                    mapping = (
                        _mapping(
                            db,
                            run=run,
                            resource=resource,
                            source_id=source_id,
                            target_entity=target_entity,
                        )
                        if source_id is not None
                        else None
                    )
                    deps[key] = (
                        {
                            "target_id": mapping.target_id,
                            "source_fingerprint": mapping.source_fingerprint,
                        }
                        if mapping is not None
                        else None
                    )
                line_dependencies.append(deps)
        bank_mapping = (
            _mapping(
                db,
                run=run,
                resource="BANK_ACCOUNTS",
                source_id=bank_source_id,
                target_entity="BANK_ACCOUNT",
            )
            if bank_source_id is not None
            else None
        )
        bill_dependencies: list[dict[str, Any]] = []
        for source_id in bill_source_ids:
            mapping = (
                _mapping(
                    db,
                    run=run,
                    resource="BILLS",
                    source_id=source_id,
                    target_entity="BILL_RELATIONSHIP",
                )
                if source_id is not None
                else None
            )
            bill_dependencies.append(
                {
                    "source_id": source_id,
                    "target_id": mapping.target_id if mapping is not None else None,
                    "source_fingerprint": (
                        mapping.source_fingerprint if mapping is not None else None
                    ),
                }
            )
        snapshot.append(
            {
                "payment_source_id": _positive_id(record.get("Id")),
                "parent_bill_source_id": _positive_id(record.get("_ParentBillId")),
                "bank_account_source_id": bank_source_id,
                "bank_account": (
                    {
                        "target_id": bank_mapping.target_id,
                        "source_fingerprint": bank_mapping.source_fingerprint,
                    }
                    if bank_mapping is not None
                    else None
                ),
                "bills": bill_dependencies,
                "lines": line_dependencies,
            }
        )
    return snapshot


def _snapshot_money(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{Decimal(value).quantize(Decimal('0.01')):.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return str(value)


def _target_check_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_check_id: int,
) -> dict[str, Any]:
    check = (
        db.query(Check)
        .filter(
            Check.id == target_check_id,
            Check.organization_id == run.organization_id,
        )
        .first()
    )
    if check is None:
        return {"target_check_id": target_check_id, "exists": False}

    bank = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == check.bank_account_id,
            BankAccount.organization_id == run.organization_id,
        )
        .first()
    )
    allocations = (
        db.query(CheckBillAllocation)
        .filter(CheckBillAllocation.check_id == check.id)
        .order_by(CheckBillAllocation.id.asc())
        .all()
    )
    allocation_snapshots: list[dict[str, Any]] = []
    for allocation in allocations:
        bill = (
            db.query(Bill)
            .filter(
                Bill.id == allocation.bill_id,
                Bill.organization_id == run.organization_id,
            )
            .first()
        )
        allocation_snapshots.append(
            {
                "allocation_id": allocation.id,
                "bill_id": allocation.bill_id,
                "amount": _snapshot_money(allocation.amount),
                "bill": (
                    {
                        "id": bill.id,
                        "status": bill.status,
                        "amount": _snapshot_money(bill.amount),
                        "amount_paid": _snapshot_money(bill.amount_paid),
                        "payee_name": bill.payee_name,
                        "payable_gl_account_id": bill.payable_gl_account_id,
                        "property_id": bill.property_id,
                        "unit_id": bill.unit_id,
                        "owner_id": bill.owner_id,
                        "is_active": bool(bill.is_active),
                        "is_reversed": bool(bill.is_reversed),
                        "deleted_at": (
                            bill.deleted_at.isoformat() if bill.deleted_at else None
                        ),
                    }
                    if bill is not None
                    else None
                ),
            }
        )

    txn = check.gl_transaction
    transaction_snapshot: dict[str, Any] | None = None
    if txn is not None:
        transaction_snapshot = {
            "id": txn.id,
            "organization_id": txn.organization_id,
            "transaction_date": (
                txn.transaction_date.isoformat() if txn.transaction_date else None
            ),
            "transaction_type": txn.transaction_type,
            "reference_number": txn.reference_number,
            "memo": txn.memo,
            "source_type": txn.source_type,
            "source_id": txn.source_id,
            "is_reversed": bool(txn.is_reversed),
            "reversal_of_id": txn.reversal_of_id,
            "entries": [
                {
                    "id": entry.id,
                    "gl_account_id": entry.gl_account_id,
                    "debit": _snapshot_money(entry.debit),
                    "credit": _snapshot_money(entry.credit),
                    "property_id": entry.property_id,
                    "unit_id": entry.unit_id,
                    "owner_id": entry.owner_id,
                }
                for entry in sorted(
                    list(txn.entries),
                    key=lambda item: item.id or 0,
                )
            ],
        }

    return {
        "target_check_id": check.id,
        "exists": True,
        "status": check.status,
        "bank_account_id": check.bank_account_id,
        "check_number": check.check_number,
        "check_date": check.check_date.isoformat(),
        "payee_name": check.payee_name,
        "memo": check.memo,
        "amount": _snapshot_money(check.amount),
        "gl_transaction_id": check.gl_transaction_id,
        "void_gl_transaction_id": check.void_gl_transaction_id,
        "voided_at": check.voided_at.isoformat() if check.voided_at else None,
        "bank": (
            {
                "id": bank.id,
                "gl_account_id": bank.gl_account_id,
                "is_active": bool(bank.is_active),
                "deleted_at": bank.deleted_at.isoformat() if bank.deleted_at else None,
            }
            if bank is not None
            else None
        ),
        "allocations": allocation_snapshots,
        "gl_transaction": transaction_snapshot,
    }


def _reviewed_target_snapshots(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    resolution_map = _normalize_resolutions(resolutions)
    snapshots: list[dict[str, Any]] = []
    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is None:
            continue
        resolution = resolution_map.get(source_id)
        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BILL_PAYMENTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        reviewed_target_id = (
            resolution["target_check_id"]
            if resolution is not None and resolution["action"] == "MATCH_EXISTING"
            else None
        )
        snapshot_target_id = (
            reviewed_target_id
            if reviewed_target_id is not None
            else durable.target_id if durable is not None else None
        )
        snapshots.append(
            {
                "source_id": source_id,
                "resolution_action": (
                    resolution["action"] if resolution is not None else None
                ),
                "review_target_check_id": reviewed_target_id,
                "target_check": (
                    _target_check_snapshot(
                        db,
                        run=run,
                        target_check_id=snapshot_target_id,
                    )
                    if snapshot_target_id is not None
                    else None
                ),
            }
        )
    return sorted(snapshots, key=lambda item: int(item["source_id"]))


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "BILL_PAYMENTS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ],
        "dependency_mappings": _dependency_snapshot(db, run=run, records=records),
        "reviewed_target_checks": _reviewed_target_snapshots(
            db,
            run=run,
            records=records,
            resolutions=resolutions,
        ),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _target_bank(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> BankAccount | None:
    return (
        db.query(BankAccount)
        .filter(
            BankAccount.id == target_id,
            BankAccount.organization_id == run.organization_id,
            BankAccount.is_active.is_(True),
            BankAccount.deleted_at.is_(None),
        )
        .first()
    )


def _target_bill(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> Bill | None:
    return (
        db.query(Bill)
        .filter(
            Bill.id == target_id,
            Bill.organization_id == run.organization_id,
            Bill.is_active.is_(True),
            Bill.deleted_at.is_(None),
            Bill.is_reversed.is_(False),
        )
        .first()
    )


def _check_match_reason(
    db: Session,
    *,
    run: PlatformMigrationRun,
    check: Check,
    mapped: dict[str, Any],
) -> str | None:
    if check.organization_id != run.organization_id or check.status != "ISSUED":
        return "Target Check is not an active issued check in the migration organization."
    if check.bank_account_id != mapped["target_bank_account_id"]:
        return "Target Check Bank Account does not match the durable Buildium mapping."
    if check.check_date.isoformat() != mapped["entry_date"]:
        return "Target Check date does not match Buildium EntryDate."
    if (check.check_number or "").strip() != mapped["check_number"]:
        return "Target Check number does not match Buildium CheckNumber."
    amount = Decimal(mapped["amount"])
    if Decimal(check.amount).quantize(Decimal("0.01")) != amount:
        return "Target Check amount does not match the Buildium payment amount."

    allocations = (
        db.query(CheckBillAllocation)
        .filter(CheckBillAllocation.check_id == check.id)
        .all()
    )
    if len(allocations) != 1:
        return "Target Check must contain exactly one Bill allocation for this bounded migration contract."
    allocation = allocations[0]
    if (
        allocation.bill_id != mapped["target_bill_id"]
        or Decimal(allocation.amount).quantize(Decimal("0.01")) != amount
    ):
        return "Target Check Bill allocation does not match the durable Buildium Bill relationship."

    bill = _target_bill(db, run=run, target_id=mapped["target_bill_id"])
    bank = _target_bank(db, run=run, target_id=mapped["target_bank_account_id"])
    if bill is None or bank is None:
        return "Mapped Bill or Bank Account is no longer active and in scope."
    if check.payee_name.strip() != bill.payee_name.strip():
        return "Target Check payee no longer matches the mapped Bill payee."
    if bill.status != "PAID":
        return "Mapped Bill is not currently PAID."
    if Decimal(bill.amount).quantize(Decimal("0.01")) != amount:
        return "Mapped Bill amount does not equal the bounded full-payment amount."
    if Decimal(bill.amount_paid).quantize(Decimal("0.01")) != amount:
        return "Mapped Bill paid amount no longer equals the bounded full-payment amount."

    txn = check.gl_transaction
    if txn is None:
        return "Target Check has no immutable GL transaction."
    if (
        txn.organization_id != run.organization_id
        or txn.transaction_type != "CHECK"
        or txn.transaction_date != check.check_date
        or txn.source_type != "check"
        or txn.source_id != check.id
        or txn.is_reversed
    ):
        return "Target Check GL transaction no longer matches the verified check-posting contract."

    entries = list(txn.entries)
    if len(entries) != 2:
        return "Target Check GL transaction must have exactly one payable debit and one bank credit for this bounded contract."
    payable_matches = [
        entry
        for entry in entries
        if entry.gl_account_id == bill.payable_gl_account_id
        and Decimal(entry.debit).quantize(Decimal("0.01")) == amount
        and Decimal(entry.credit).quantize(Decimal("0.01")) == Decimal("0.00")
        and entry.property_id == bill.property_id
        and entry.unit_id == bill.unit_id
        and entry.owner_id == bill.owner_id
    ]
    bank_matches = [
        entry
        for entry in entries
        if entry.gl_account_id == bank.gl_account_id
        and Decimal(entry.credit).quantize(Decimal("0.01")) == amount
        and Decimal(entry.debit).quantize(Decimal("0.01")) == Decimal("0.00")
    ]
    if len(payable_matches) != 1 or len(bank_matches) != 1:
        return "Target Check GL debit/credit lines no longer match the verified payment posting."
    return None


def _map_record(
    db: Session,
    *,
    run: PlatformMigrationRun,
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Bill Payment Id must be a positive integer.", []

    bank_source_id = _positive_id(record.get("BankAccountId"))
    if bank_source_id is None:
        return None, "Buildium Bill Payment requires a positive BankAccountId.", []
    bank_mapping = _mapping(
        db,
        run=run,
        resource="BANK_ACCOUNTS",
        source_id=bank_source_id,
        target_entity="BANK_ACCOUNT",
    )
    if bank_mapping is None:
        return None, f"Bill Payment requires durable Buildium Bank Account mapping {bank_source_id}.", []
    bank = _target_bank(db, run=run, target_id=bank_mapping.target_id)
    if bank is None:
        return None, "Mapped Buildium Bank Account is no longer active in organization scope.", []

    entry_date, error = _date(record.get("EntryDate"), field="EntryDate")
    if error:
        return None, error, []

    check_number = _clean(record.get("CheckNumber"))
    if check_number is None:
        return None, (
            "This bounded Bill Payment batch requires a documented CheckNumber; "
            "electronic or non-check payments remain blocked."
        ), []
    if len(check_number) > 40:
        return None, "Buildium CheckNumber exceeds the target Check 40-character limit.", []

    paid_bill_ids = record.get("PaidBillIds")
    if not isinstance(paid_bill_ids, list) or len(paid_bill_ids) != 1:
        return None, (
            "This bounded Bill Payment batch supports exactly one fully paid Buildium Bill per check; "
            "multi-bill or ambiguous payments remain blocked."
        ), []
    bill_source_id = _positive_id(paid_bill_ids[0])
    if bill_source_id is None:
        return None, "PaidBillIds must contain one positive Buildium Bill ID.", []

    parent_bill_source_id: str | None = None
    if "_ParentBillId" in record:
        parent_bill_source_id = _positive_id(record.get("_ParentBillId"))
        if parent_bill_source_id is None:
            return None, "Buildium Bill Payment nested parent Bill ID is invalid.", []
        if parent_bill_source_id != bill_source_id:
            return None, (
                "Buildium Bill Payment nested parent Bill does not match the single PaidBillIds relationship."
            ), []

    bill_mapping = _mapping(
        db,
        run=run,
        resource="BILLS",
        source_id=bill_source_id,
        target_entity="BILL_RELATIONSHIP",
    )
    if bill_mapping is None:
        return None, f"Bill Payment requires durable Buildium Bill mapping {bill_source_id}.", []
    bill = _target_bill(db, run=run, target_id=bill_mapping.target_id)
    if bill is None:
        return None, "Mapped Buildium Bill is no longer active in organization scope.", []

    credits = record.get("AppliedVendorCredits")
    if credits not in (None, []):
        if not isinstance(credits, list):
            return None, "AppliedVendorCredits must be a list when supplied.", []
        return None, (
            "Buildium Bill Payments with applied Vendor Credits are not representable by the target Check allocation contract."
        ), []

    lines = record.get("Lines")
    if not isinstance(lines, list) or not lines:
        return None, "Buildium Bill Payment Lines must contain at least one line.", []
    if len(lines) > 200:
        return None, "Buildium Bill Payment Lines exceed the bounded 200-line migration limit.", []

    source_allocations: Counter[tuple[int, int | None, int | None, str]] = Counter()
    total = Decimal("0.00")
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            return None, f"Bill Payment line {index} must be an object.", []
        entity = line.get("AccountingEntity")
        if not isinstance(entity, dict) or entity.get("AccountingEntityType") != "Rental":
            return None, (
                f"Bill Payment line {index} must use documented Rental accounting-entity semantics."
            ), []
        property_source_id = _positive_id(entity.get("Id"))
        if property_source_id is None:
            return None, f"Bill Payment line {index} requires a positive Rental AccountingEntity Id.", []
        property_mapping = _mapping(
            db,
            run=run,
            resource="PROPERTIES",
            source_id=property_source_id,
            target_entity="PROPERTY",
        )
        if property_mapping is None:
            return None, f"Bill Payment line {index} requires durable Property mapping {property_source_id}.", []
        target_property = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
            )
            .first()
        )
        if target_property is None:
            return None, f"Bill Payment line {index} mapped Property is no longer active and in scope.", []

        unit_source_id = _positive_id(entity.get("UnitId"))
        target_unit_id: int | None = None
        if entity.get("UnitId") not in (None, 0, "") and unit_source_id is None:
            return None, f"Bill Payment line {index} UnitId must be a positive integer when supplied.", []
        if unit_source_id is not None:
            unit_mapping = _mapping(
                db,
                run=run,
                resource="UNITS",
                source_id=unit_source_id,
                target_entity="UNIT",
            )
            if unit_mapping is None:
                return None, f"Bill Payment line {index} requires durable Unit mapping {unit_source_id}.", []
            unit = (
                db.query(Unit)
                .filter(
                    Unit.id == unit_mapping.target_id,
                    Unit.property_id == target_property.id,
                    Unit.is_active.is_(True),
                )
                .first()
            )
            if unit is None:
                return None, f"Bill Payment line {index} mapped Unit no longer belongs to the mapped Property.", []
            target_unit_id = unit.id

        gl_source_id = _positive_id(line.get("GLAccountId"))
        if gl_source_id is None:
            return None, f"Bill Payment line {index} requires a positive GLAccountId.", []
        gl_mapping = _mapping(
            db,
            run=run,
            resource="GL_ACCOUNTS",
            source_id=gl_source_id,
            target_entity="GL_ACCOUNT",
        )
        if gl_mapping is None:
            return None, f"Bill Payment line {index} requires durable GL Account mapping {gl_source_id}.", []
        gl = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
            )
            .first()
        )
        if gl is None:
            return None, f"Bill Payment line {index} mapped GL Account is no longer in scope.", []

        amount, amount_error = _money(line.get("Amount"), field=f"Lines[{index}].Amount")
        if amount_error:
            return None, amount_error, []
        total += amount
        source_allocations[
            (gl.id, target_property.id, target_unit_id, f"{amount:.2f}")
        ] += 1

    target_lines = (
        db.query(BillLine)
        .filter(
            BillLine.organization_id == run.organization_id,
            BillLine.bill_id == bill.id,
        )
        .all()
    )
    target_allocations = Counter(
        (
            line.gl_account_id,
            line.property_id,
            line.unit_id,
            f"{Decimal(line.amount).quantize(Decimal('0.01')):.2f}",
        )
        for line in target_lines
    )
    if source_allocations != target_allocations:
        return None, (
            "Buildium Bill Payment line relationships do not exactly match the already-mapped target Bill lines."
        ), []

    total = total.quantize(Decimal("0.01"))
    if Decimal(bill.amount).quantize(Decimal("0.01")) != total:
        return None, (
            "This bounded Bill Payment batch requires a full single-bill payment whose line total exactly equals the mapped Bill amount."
        ), []
    if bill.status != "PAID" or Decimal(bill.amount_paid).quantize(Decimal("0.01")) != total:
        return None, (
            "Mapped target Bill must already be fully PAID for relationship-only reconciliation."
        ), []

    candidates = (
        db.query(Check)
        .filter(
            Check.organization_id == run.organization_id,
            Check.bank_account_id == bank.id,
            Check.check_date == entry_date,
            Check.check_number == check_number,
            Check.status == "ISSUED",
        )
        .order_by(Check.id.asc())
        .limit(10)
        .all()
    )
    candidate_ids = [
        check.id
        for check in candidates
        if _check_match_reason(
            db,
            run=run,
            check=check,
            mapped={
                "target_bank_account_id": bank.id,
                "target_bill_id": bill.id,
                "entry_date": entry_date.isoformat(),
                "check_number": check_number,
                "amount": f"{total:.2f}",
            },
        )
        is None
    ]

    warnings = [
        "Relationship-only reconciliation: no Check, Bill, payment, bank movement, Vendor Credit, or GL history is created or updated.",
        "Only one fully paid Bill, one documented CheckNumber, no Vendor Credits, and exact Bill-line mappings are supported in this bounded batch.",
        "Buildium Memo and any provider response body remain source evidence only and are never persisted in migration metadata or audit.",
    ]
    if candidate_ids:
        warnings.append(
            "Possible exact existing Check relationship found; explicit MATCH_EXISTING review is still required."
        )
    else:
        warnings.append(
            "No exact existing target Check satisfies the bounded payment contract; this batch does not create one."
        )

    return (
        {
            "source_id": source_id,
            "parent_bill_source_id": parent_bill_source_id,
            "target_bank_account_id": bank.id,
            "target_bill_id": bill.id,
            "entry_date": entry_date.isoformat(),
            "check_number": check_number,
            "amount": f"{total:.2f}",
            "line_count": len(lines),
            "candidate_check_ids": candidate_ids,
            "vendor_credits_applied": False,
            "full_single_bill_check_only": True,
        },
        None,
        warnings,
    )


def dry_run_bill_payments(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> BillPaymentDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumBillPaymentMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumBillPaymentMigrationError(
            "At least one Buildium Bill Payment record is required."
        )

    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    reviewable = skipped_review = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is not None and source_id in seen:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Duplicate Buildium Bill Payment Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if source_id is not None:
            seen.add(source_id)

        mapped, reason, warnings = _map_record(db, run=run, record=record)
        if mapped is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": reason,
                    "mapped": None,
                    "warnings": warnings,
                }
            )
            invalid += 1
            warning_count += len(warnings)
            continue

        source_id = mapped["source_id"]
        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BILL_PAYMENTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_check_id"] if resolution else None

        if durable is not None:
            if durable.target_entity != "CHECK_PAYMENT_RELATIONSHIP":
                raise BuildiumBillPaymentMigrationError(
                    "Buildium Bill Payment mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumBillPaymentMigrationError(
                    f"Buildium source Bill Payment ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            check = (
                db.query(Check)
                .filter(
                    Check.id == durable.target_id,
                    Check.organization_id == run.organization_id,
                )
                .first()
            )
            if check is None:
                raise BuildiumBillPaymentMigrationError(
                    "Previously mapped target Check is missing or out of organization scope."
                )
            mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
            if mismatch is not None:
                raise BuildiumBillPaymentMigrationError(
                    "Previously mapped target Check no longer satisfies the Buildium Bill Payment relationship: "
                    + mismatch
                )
            warnings.append(
                f"Buildium source Bill Payment ID {source_id} is already durably mapped to local Check #{check.id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            check = (
                db.query(Check)
                .filter(
                    Check.id == target_id,
                    Check.organization_id == run.organization_id,
                )
                .first()
            )
            if check is None:
                raise BuildiumBillPaymentMigrationError(
                    f"Reviewed target Check #{target_id} is not in the target organization."
                )
            mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
            if mismatch is not None:
                raise BuildiumBillPaymentMigrationError(
                    "Reviewed target Check does not satisfy the exact Buildium Bill Payment relationship contract: "
                    + mismatch
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Check #{check.id}; commit creates durable relationship metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Bill Payment review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_check_id": None,
                }
            )
            skipped_review += 1
            warning_count += len(warnings)
            continue

        rows.append(
            {
                "source_id": source_id,
                "reviewable": True,
                "reason": None,
                "mapped": mapped,
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_check_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - seen, key=int)
    if unknown:
        raise BuildiumBillPaymentMigrationError(
            "Bill Payment review contains source IDs not present in this dry run: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BILL_PAYMENTS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped_review,
        "invalid": invalid,
        "warning_count": warning_count,
        "target_mutation": False,
        "full_single_bill_check_only": True,
        "partial_payments_supported": False,
        "multi_bill_payments_supported": False,
        "vendor_credit_payments_supported": False,
        "electronic_noncheck_payments_supported": False,
    }
    run.last_dry_run_fingerprint = fingerprint
    run.last_dry_run_summary = summary
    run.status = "DRY_RUN_READY"
    db.flush()
    return BillPaymentDryRunResult(
        fingerprint,
        replayed,
        len(records),
        reviewable,
        skipped_review,
        invalid,
        warning_count,
        rows,
        summary,
    )


def commit_bill_payments(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> BillPaymentCommitResult:
    preview = dry_run_bill_payments(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.fingerprint != expected_fingerprint:
        raise BuildiumBillPaymentMigrationError(
            "Buildium Bill Payment dry run is stale; run review again before commit."
        )
    if preview.invalid:
        raise BuildiumBillPaymentMigrationError(
            "Buildium Bill Payment commit is blocked while invalid or unsupported source rows remain."
        )

    resolution_map = _normalize_resolutions(resolutions)
    valid = [row for row in preview.rows if row["mapped"] is not None]
    missing: list[str] = []
    for row in valid:
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BILL_PAYMENTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and (
            source_id not in resolution_map
            or resolution_map[source_id]["action"] != "MATCH_EXISTING"
        ):
            missing.append(source_id)
    if missing:
        raise BuildiumBillPaymentMigrationError(
            "Bill Payment relationship mapping requires explicit MATCH_EXISTING or SKIP review for every supported source row: "
            + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False
    for row in valid:
        source_id = str(row["source_id"])
        mapped = row["mapped"]
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BILL_PAYMENTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "CHECK_PAYMENT_RELATIONSHIP":
                raise BuildiumBillPaymentMigrationError(
                    "Buildium Bill Payment mapping is inconsistent."
                )
            check = (
                db.query(Check)
                .filter(
                    Check.id == prior.target_id,
                    Check.organization_id == run.organization_id,
                )
                .first()
            )
            if check is None:
                raise BuildiumBillPaymentMigrationError(
                    "Previously mapped target Check is missing or out of organization scope."
                )
            mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
            if mismatch is not None:
                raise BuildiumBillPaymentMigrationError(
                    "Previously mapped target Check changed after dry run: " + mismatch
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_check_id": check.id,
                    "replayed": True,
                }
            )
            continue

        target_id = resolution_map[source_id]["target_check_id"]
        check = (
            db.query(Check)
            .filter(
                Check.id == target_id,
                Check.organization_id == run.organization_id,
            )
            .first()
        )
        if check is None:
            raise BuildiumBillPaymentMigrationError(
                f"Reviewed target Check #{target_id} is no longer in organization scope."
            )
        mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
        if mismatch is not None:
            raise BuildiumBillPaymentMigrationError(
                "Reviewed target Check changed after dry run: " + mismatch
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BILL_PAYMENTS",
                source_id=source_id,
                target_entity="CHECK_PAYMENT_RELATIONSHIP",
                target_id=check.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_check_id": check.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "BILL_PAYMENTS_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "BILL_PAYMENTS_REVIEWED"
        db.flush()
        review_recorded = True

    return BillPaymentCommitResult(
        preview.fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
