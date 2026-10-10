"""Buildium bank-check existing-target reconciliation for Phase 4.14.

This bounded adapter reconciles documented Buildium bank Check responses to
already-existing target Checks. It supports only Rental-scoped Vendor checks
whose complete bank, payee, property/unit and GL line semantics can be proven.
It never creates or changes checks, bills, GL history, bank balances, cleared
state, provider credentials or external settlement history.
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
from app.models.check import Check
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.vendor import Vendor


class BuildiumCheckMigrationError(ValueError):
    pass


CENT = Decimal("0.01")
MAX_ABS_MONEY = Decimal("999999999999.99")


@dataclass(frozen=True)
class CheckDryRunResult:
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
class CheckCommitResult:
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
    if value is None or isinstance(value, bool):
        return None, f"{field} must be an explicit positive monetary amount."
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field} must be an explicit positive monetary amount."
    if not raw.is_finite() or raw <= 0 or abs(raw) > MAX_ABS_MONEY:
        return None, f"{field} must be a finite positive monetary amount."
    normalized = raw.quantize(CENT)
    if normalized != raw:
        return None, f"{field} must have no more than two decimal places."
    return normalized, None


def _date_value(value: Any, *, field: str) -> tuple[date | None, str | None]:
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
        raise BuildiumCheckMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _target_bank(db: Session, *, run: PlatformMigrationRun, target_id: int) -> BankAccount | None:
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


def _target_vendor(db: Session, *, run: PlatformMigrationRun, target_id: int) -> Vendor | None:
    return (
        db.query(Vendor)
        .filter(
            Vendor.id == target_id,
            Vendor.organization_id == run.organization_id,
            Vendor.is_active.is_(True),
            Vendor.deleted_at.is_(None),
        )
        .first()
    )


def _target_gl(db: Session, *, run: PlatformMigrationRun, target_id: int) -> GLAccount | None:
    return (
        db.query(GLAccount)
        .filter(
            GLAccount.id == target_id,
            GLAccount.organization_id == run.organization_id,
            GLAccount.is_active.is_(True),
        )
        .first()
    )


def _normalize_resolutions(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumCheckMigrationError(
                "Bank Check review requires unique positive source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumCheckMigrationError(
                "Bank Check review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_check_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumCheckMigrationError(
                    "MATCH_EXISTING requires a positive target_check_id."
                )
        elif target_id is not None:
            raise BuildiumCheckMigrationError(
                "target_check_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_check_id": target_id,
        }
    return result


def _source_record(
    db: Session,
    *,
    run: PlatformMigrationRun,
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    bank_source_id = _positive_id(record.get("SourceBankAccountId"))
    check_number = _clean(record.get("CheckNumber"))
    entry_date, date_error = _date_value(record.get("EntryDate"), field="EntryDate")
    total, total_error = _money(record.get("TotalAmount"), field="TotalAmount")

    if source_id is None:
        return None, "Buildium Check Id must be a positive integer."
    if bank_source_id is None:
        return None, "SourceBankAccountId retrieval context must be a positive integer."
    if check_number is None:
        return None, "Buildium CheckNumber is required for exact target reconciliation."
    if len(check_number) > 40:
        return None, "Buildium CheckNumber exceeds the target Check 40-character limit."
    if date_error:
        return None, date_error
    if total_error:
        return None, total_error

    bank_mapping = _mapping(
        db, run=run, resource="BANK_ACCOUNTS", source_id=bank_source_id, target_entity="BANK_ACCOUNT"
    )
    if bank_mapping is None:
        return None, "Bank Check reconciliation requires a durable same-run Buildium Bank Account mapping."
    bank = _target_bank(db, run=run, target_id=bank_mapping.target_id)
    if bank is None:
        return None, "Mapped Bank Account is no longer active in the target organization."

    payee = record.get("Payee")
    if not isinstance(payee, dict) or _clean(payee.get("Type")) != "Vendor":
        return None, "This bounded Bank Check batch supports only documented Vendor payees."
    vendor_source_id = _positive_id(payee.get("Id"))
    if vendor_source_id is None:
        return None, "Buildium Vendor payee Id must be a positive integer."
    vendor_mapping = _mapping(
        db, run=run, resource="VENDORS", source_id=vendor_source_id, target_entity="VENDOR"
    )
    if vendor_mapping is None:
        return None, "Bank Check reconciliation requires a durable same-run Buildium Vendor mapping."
    vendor = _target_vendor(db, run=run, target_id=vendor_mapping.target_id)
    if vendor is None:
        return None, "Mapped Vendor is no longer active in the target organization."

    lines = record.get("Lines")
    if not isinstance(lines, list) or not lines:
        return None, "Buildium Check Lines must contain at least one line."

    mapped_lines: list[dict[str, Any]] = []
    source_total = Decimal("0.00")
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            return None, f"Buildium Check line {index} must be an object."
        line_amount, amount_error = _money(line.get("Amount"), field=f"Lines[{index}].Amount")
        if amount_error:
            return None, amount_error
        gl_source_id = _positive_id(line.get("GLAccountId"))
        if gl_source_id is None:
            return None, f"Buildium Check line {index} requires a positive GLAccountId."
        gl_mapping = _mapping(
            db, run=run, resource="GL_ACCOUNTS", source_id=gl_source_id, target_entity="GL_ACCOUNT"
        )
        if gl_mapping is None:
            return None, f"Buildium Check line {index} requires durable GL Account mapping {gl_source_id}."
        gl = _target_gl(db, run=run, target_id=gl_mapping.target_id)
        if gl is None:
            return None, f"Buildium Check line {index} mapped GL Account is no longer active."

        entity = line.get("AccountingEntity")
        if not isinstance(entity, dict) or _clean(entity.get("AccountingEntityType")) != "Rental":
            return None, (
                "This bounded Bank Check batch supports only Rental accounting-entity lines; "
                "Company and Association checks remain blocked."
            )
        property_source_id = _positive_id(entity.get("Id"))
        if property_source_id is None:
            return None, f"Buildium Check line {index} requires a positive Rental AccountingEntity Id."
        property_mapping = _mapping(
            db, run=run, resource="PROPERTIES", source_id=property_source_id, target_entity="PROPERTY"
        )
        if property_mapping is None:
            return None, f"Buildium Check line {index} requires durable Property mapping {property_source_id}."
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
            return None, f"Buildium Check line {index} mapped Property is no longer active and in scope."

        unit_obj = entity.get("Unit")
        unit_source_id = None
        if unit_obj not in (None, {}):
            if not isinstance(unit_obj, dict):
                return None, f"Buildium Check line {index} Unit must be an object when supplied."
            unit_source_id = _positive_id(unit_obj.get("Id"))
            if unit_source_id is None:
                return None, f"Buildium Check line {index} Unit Id must be a positive integer."
        target_unit_id = None
        unit_mapping = None
        if unit_source_id is not None:
            unit_mapping = _mapping(
                db, run=run, resource="UNITS", source_id=unit_source_id, target_entity="UNIT"
            )
            if unit_mapping is None:
                return None, f"Buildium Check line {index} requires durable Unit mapping {unit_source_id}."
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
                return None, f"Buildium Check line {index} mapped Unit no longer belongs to the mapped Property."
            target_unit_id = unit.id

        source_total += line_amount
        mapped_lines.append(
            {
                "source_gl_account_id": gl_source_id,
                "target_gl_account_id": gl.id,
                "gl_mapping_fingerprint": gl_mapping.source_fingerprint,
                "source_property_id": property_source_id,
                "target_property_id": target_property.id,
                "property_mapping_fingerprint": property_mapping.source_fingerprint,
                "source_unit_id": unit_source_id,
                "target_unit_id": target_unit_id,
                "unit_mapping_fingerprint": unit_mapping.source_fingerprint if unit_mapping else None,
                "amount": line_amount,
            }
        )

    if source_total != total:
        return None, "Buildium Check TotalAmount must exactly equal the sum of documented Lines."

    return {
        "source_id": source_id,
        "source_bank_account_id": bank_source_id,
        "target_bank_account_id": bank.id,
        "bank_mapping_fingerprint": bank_mapping.source_fingerprint,
        "vendor_source_id": vendor_source_id,
        "target_vendor_id": vendor.id,
        "vendor_mapping_fingerprint": vendor_mapping.source_fingerprint,
        "vendor_name": vendor.company_name,
        "check_number": check_number,
        "entry_date": entry_date,
        "total_amount": total,
        "lines": mapped_lines,
    }, None


def _target_check(db: Session, *, run: PlatformMigrationRun, target_id: int) -> Check | None:
    return (
        db.query(Check)
        .filter(Check.id == target_id, Check.organization_id == run.organization_id)
        .first()
    )


def _expected_entries(mapped: dict[str, Any], bank_gl_account_id: int) -> Counter:
    rows = Counter()
    for line in mapped["lines"]:
        rows[
            (
                line["target_gl_account_id"],
                line["target_property_id"],
                line["target_unit_id"],
                None,
                str(line["amount"]),
                "0.00",
            )
        ] += 1
    rows[(bank_gl_account_id, None, None, None, "0.00", str(mapped["total_amount"]))] += 1
    return rows


def _actual_entries(entries: list[GLEntry]) -> Counter:
    rows = Counter()
    for entry in entries:
        rows[
            (
                entry.gl_account_id,
                entry.property_id,
                entry.unit_id,
                entry.owner_id,
                str(Decimal(entry.debit or 0).quantize(CENT)),
                str(Decimal(entry.credit or 0).quantize(CENT)),
            )
        ] += 1
    return rows


def _check_match_reason(
    db: Session,
    *,
    run: PlatformMigrationRun,
    check: Check,
    mapped: dict[str, Any],
) -> str | None:
    if check.status != "ISSUED":
        return "Target Check is not currently ISSUED."
    if check.bank_account_id != mapped["target_bank_account_id"]:
        return "Target Check Bank Account does not match the durable Buildium mapping."
    if (check.check_number or "").strip() != mapped["check_number"]:
        return "Target Check number does not match Buildium CheckNumber."
    if check.check_date != mapped["entry_date"]:
        return "Target Check date does not match Buildium EntryDate."
    if Decimal(check.amount or 0).quantize(CENT) != mapped["total_amount"]:
        return "Target Check amount does not match Buildium TotalAmount."
    if (check.payee_name or "").strip().casefold() != (mapped["vendor_name"] or "").strip().casefold():
        return "Target Check payee does not match the mapped Buildium Vendor."
    if check.allocations:
        return (
            "Target Check has Bill allocations that the Buildium bank Check source does not "
            "identify; this bounded batch will not infer those relationships."
        )
    if check.gl_transaction_id is None:
        return "Target Check has no immutable GL transaction to reconcile."

    txn = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.id == check.gl_transaction_id,
            GLTransaction.organization_id == run.organization_id,
            GLTransaction.transaction_type == "CHECK",
            GLTransaction.source_type == "check",
            GLTransaction.source_id == check.id,
            GLTransaction.transaction_date == mapped["entry_date"],
            GLTransaction.reference_number == mapped["check_number"],
            GLTransaction.is_reversed.is_(False),
            GLTransaction.reversal_of_id.is_(None),
        )
        .first()
    )
    if txn is None:
        return "Target Check immutable GL transaction no longer matches the source identity/date."
    bank = _target_bank(db, run=run, target_id=mapped["target_bank_account_id"])
    if bank is None:
        return "Mapped target Bank Account is no longer active."
    entries = (
        db.query(GLEntry)
        .filter(
            GLEntry.transaction_id == txn.id,
            GLEntry.organization_id == run.organization_id,
        )
        .all()
    )
    if _actual_entries(entries) != _expected_entries(mapped, bank.gl_account_id):
        return "Target Check GL lines no longer exactly match the reviewed Buildium Check lines."
    return None


def _target_snapshot(db: Session, *, run: PlatformMigrationRun, target_id: int) -> dict[str, Any] | None:
    check = _target_check(db, run=run, target_id=target_id)
    if check is None:
        return None
    txn = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.id == check.gl_transaction_id,
            GLTransaction.organization_id == run.organization_id,
        )
        .first()
        if check.gl_transaction_id is not None
        else None
    )
    entries = (
        db.query(GLEntry)
        .filter(
            GLEntry.transaction_id == txn.id,
            GLEntry.organization_id == run.organization_id,
        )
        .order_by(GLEntry.id.asc())
        .all()
        if txn is not None
        else []
    )
    return {
        "check_id": check.id,
        "bank_account_id": check.bank_account_id,
        "check_number": check.check_number,
        "check_date": check.check_date.isoformat(),
        "payee_name": check.payee_name,
        "amount": str(Decimal(check.amount or 0).quantize(CENT)),
        "status": check.status,
        "gl_transaction_id": check.gl_transaction_id,
        "allocation_count": len(check.allocations),
        "transaction": (
            {
                "id": txn.id,
                "date": txn.transaction_date.isoformat(),
                "type": txn.transaction_type,
                "reference": txn.reference_number,
                "source_type": txn.source_type,
                "source_id": txn.source_id,
                "is_reversed": bool(txn.is_reversed),
                "reversal_of_id": txn.reversal_of_id,
            }
            if txn is not None
            else None
        ),
        "entries": [
            {
                "gl_account_id": row.gl_account_id,
                "property_id": row.property_id,
                "unit_id": row.unit_id,
                "owner_id": row.owner_id,
                "debit": str(Decimal(row.debit or 0).quantize(CENT)),
                "credit": str(Decimal(row.credit or 0).quantize(CENT)),
            }
            for row in entries
        ],
    }


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    dependencies: list[dict[str, Any]] = []
    for record in records:
        mapped, reason = _source_record(db, run=run, record=record)
        dependencies.append(
            {
                "source_id": _positive_id(record.get("Id")),
                "mapped": mapped,
                "invalid_reason": reason,
            }
        )
    reviewed_targets = [
        {
            "source_id": key,
            "target": _target_snapshot(
                db,
                run=run,
                target_id=resolution_map[key]["target_check_id"],
            )
            if resolution_map[key]["action"] == "MATCH_EXISTING"
            else None,
        }
        for key in sorted(resolution_map, key=int)
    ]
    payload = {
        "provider": "BUILDIUM",
        "resource": "BANK_CHECKS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [resolution_map[key] for key in sorted(resolution_map, key=int)],
        "dependencies": dependencies,
        "reviewed_targets": reviewed_targets,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def dry_run_checks(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> CheckDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumCheckMigrationError("Buildium Check migration requires a BUILDIUM run.")
    resolution_map = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = (
        run.last_dry_run_fingerprint == fingerprint
        and isinstance(run.last_dry_run_summary, dict)
        and run.last_dry_run_summary.get("resource") == "BANK_CHECKS"
    )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is not None:
            if source_id in seen:
                raise BuildiumCheckMigrationError(
                    f"Duplicate Buildium Check source ID {source_id}."
                )
            seen.add(source_id)

        mapped, reason = _source_record(db, run=run, record=record)
        if mapped is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": reason,
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_check_id": None,
                }
            )
            invalid += 1
            continue

        source_id = mapped["source_id"]
        prior = _mapping(
            db, run=run, resource="BANK_CHECKS", source_id=source_id,
            target_entity="CHECK_PAYMENT_RELATIONSHIP"
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_check_id"] if resolution else None

        if prior is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != prior.target_id
            ):
                raise BuildiumCheckMigrationError(
                    f"Buildium Check source ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            action = "MATCH_EXISTING"
            target_id = prior.target_id

        warnings: list[str] = []
        if action == "SKIP":
            skipped += 1
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped by migration review.",
                    "mapped": mapped,
                    "warnings": warnings,
                    "resolution_action": action,
                    "resolution_target_check_id": None,
                }
            )
            continue

        if action == "MATCH_EXISTING":
            check = _target_check(db, run=run, target_id=target_id)
            if check is None:
                raise BuildiumCheckMigrationError(
                    f"Reviewed target Check {target_id} is not in the target organization."
                )
            mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
            if mismatch is not None:
                raise BuildiumCheckMigrationError(
                    "Reviewed target Check no longer matches the Buildium source: " + mismatch
                )
        else:
            warnings.append(
                "Possible exact existing target Check must be selected explicitly; "
                "this batch never creates or guesses a Check."
            )

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
        raise BuildiumCheckMigrationError(
            "Bank Check review contains source IDs not present in this dry run: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BANK_CHECKS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "target_checks_created": False,
        "bill_allocations_created": False,
        "gl_history_created": False,
        "external_settlement_verified": False,
        "supported_scope": "RENTAL_VENDOR_CHECK_WITHOUT_TARGET_BILL_ALLOCATIONS",
    }
    run.last_dry_run_fingerprint = fingerprint
    run.last_dry_run_summary = summary
    run.status = "DRY_RUN_READY"
    db.flush()
    return CheckDryRunResult(
        fingerprint, replayed, len(records), reviewable, skipped,
        invalid, warning_count, rows, summary
    )


def commit_checks(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> CheckCommitResult:
    preview = dry_run_checks(db, run=run, records=records, resolutions=resolutions)
    if preview.fingerprint != expected_fingerprint:
        raise BuildiumCheckMigrationError(
            "Buildium Bank Check dry run is stale; review the current source and target again."
        )
    resolution_map = _normalize_resolutions(resolutions)
    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False

    for row in preview.rows:
        if row["mapped"] is None or row["resolution_action"] == "SKIP":
            continue
        source_id = str(row["source_id"])
        mapped = row["mapped"]
        prior = _mapping(
            db, run=run, resource="BANK_CHECKS", source_id=source_id,
            target_entity="CHECK_PAYMENT_RELATIONSHIP"
        )
        if prior is not None:
            check = _target_check(db, run=run, target_id=prior.target_id)
            if check is None:
                raise BuildiumCheckMigrationError(
                    "Previously mapped target Check is missing or out of organization scope."
                )
            mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
            if mismatch is not None:
                raise BuildiumCheckMigrationError(
                    "Previously mapped target Check no longer matches source: " + mismatch
                )
            rows.append(
                {"source_id": source_id, "target_check_id": check.id, "replayed": True}
            )
            continue

        resolution = resolution_map.get(source_id)
        if resolution is None or resolution["action"] != "MATCH_EXISTING":
            raise BuildiumCheckMigrationError(
                "Bank Check mapping requires explicit MATCH_EXISTING or SKIP review for every supported source row."
            )
        check = _target_check(db, run=run, target_id=resolution["target_check_id"])
        if check is None:
            raise BuildiumCheckMigrationError("Reviewed target Check is out of organization scope.")
        mismatch = _check_match_reason(db, run=run, check=check, mapped=mapped)
        if mismatch is not None:
            raise BuildiumCheckMigrationError(
                "Reviewed target Check changed after dry run: " + mismatch
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BANK_CHECKS",
                source_id=source_id,
                target_entity="CHECK_PAYMENT_RELATIONSHIP",
                target_id=check.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {"source_id": source_id, "target_check_id": check.id, "replayed": False}
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "BANK_CHECKS_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "BANK_CHECKS_REVIEWED"
        db.flush()
        review_recorded = True

    return CheckCommitResult(
        preview.fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
