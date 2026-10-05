"""Buildium bank-transfer existing-target reconciliation for Phase 4.14.

Consumes the documented Buildium bank transfer shape plus source-bank path
context and maps only to an already-existing target GLTransaction TRANSFER.
No bank account, GL transaction, GL entry, balance, clearing, or reconciliation
state is created or changed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit


class BuildiumBankTransferMigrationError(ValueError):
    pass


CENT = Decimal("0.01")
MAX_ABS_MONEY = Decimal("999999999999.99")


@dataclass(frozen=True)
class BankTransferDryRunResult:
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
class BankTransferCommitResult:
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


def _money(value: Any) -> tuple[Decimal | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, "TotalAmount must be an explicit positive monetary amount."
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, "TotalAmount must be an explicit positive monetary amount."
    if not raw.is_finite() or raw <= 0 or abs(raw) > MAX_ABS_MONEY:
        return None, "TotalAmount must be a finite positive monetary amount."
    normalized = raw.quantize(CENT)
    if normalized != raw:
        return None, "TotalAmount must have no more than two decimal places."
    return normalized, None


def _date_value(value: Any) -> tuple[date | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, "EntryDate is required."
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, "EntryDate must be an ISO date (YYYY-MM-DD)."


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
        raise BuildiumBankTransferMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _source_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    source_bank_id = _positive_id(record.get("SourceBankAccountId"))
    destination_bank_id = _positive_id(record.get("TransferToBankAccountId"))
    entry_date, date_error = _date_value(record.get("EntryDate"))
    amount, amount_error = _money(record.get("TotalAmount"))

    entity = record.get("AccountingEntity")
    if not isinstance(entity, dict):
        return None, "AccountingEntity must contain the documented Buildium transfer accounting entity."
    entity_type = _clean(entity.get("AccountingEntityType"))
    property_source_id = _positive_id(entity.get("Id"))
    unit = entity.get("Unit")
    unit_source_id = None
    if unit is not None:
        if not isinstance(unit, dict):
            return None, "AccountingEntity.Unit must be an object when provided."
        raw_unit_id = unit.get("Id")
        if raw_unit_id not in (None, 0, "0", ""):
            unit_source_id = _positive_id(raw_unit_id)
            if unit_source_id is None:
                return None, "AccountingEntity.Unit.Id must be a positive integer when provided."

    errors = [
        item
        for item in (
            None if source_id is not None else "Buildium transfer Id must be a positive integer.",
            None if source_bank_id is not None else "SourceBankAccountId retrieval context must be a positive integer.",
            None if destination_bank_id is not None else "TransferToBankAccountId must be a positive integer.",
            date_error,
            amount_error,
            None if entity_type == "Rental" else "This bounded batch supports only Buildium Rental bank transfers.",
            None if property_source_id is not None else "Rental AccountingEntity.Id must be a positive Buildium Property Id.",
        )
        if item
    ]
    if source_bank_id is not None and destination_bank_id == source_bank_id:
        errors.append("Source and destination Buildium Bank Account IDs must be different.")
    if errors:
        return None, " ".join(errors)

    return {
        "source_id": source_id,
        "source_bank_source_id": source_bank_id,
        "destination_bank_source_id": destination_bank_id,
        "entry_date": entry_date,
        "amount": amount,
        "property_source_id": property_source_id,
        "unit_source_id": unit_source_id,
    }, None


def _normalize_resolutions(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumBankTransferMigrationError(
                "Bank Transfer review requires unique positive source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBankTransferMigrationError(
                "Bank Transfer review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_gl_transaction_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumBankTransferMigrationError(
                    "MATCH_EXISTING requires a positive target_gl_transaction_id."
                )
        elif target_id is not None:
            raise BuildiumBankTransferMigrationError(
                "target_gl_transaction_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_gl_transaction_id": target_id,
        }
    return result


def _dependency(
    db: Session,
    *,
    run: PlatformMigrationRun,
    resource: str,
    source_id: str | None,
    target_entity: str,
) -> PlatformMigrationItem | None:
    if source_id is None:
        return None
    return _mapping(
        db, run=run, resource=resource, source_id=source_id, target_entity=target_entity
    )


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


def _target_property(db: Session, *, run: PlatformMigrationRun, target_id: int) -> Property | None:
    return (
        db.query(Property)
        .filter(
            Property.id == target_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
        .first()
    )


def _target_unit(
    db: Session, *, run: PlatformMigrationRun, target_id: int, property_id: int
) -> Unit | None:
    return (
        db.query(Unit)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Unit.id == target_id,
            Unit.property_id == property_id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
            Property.organization_id == run.organization_id,
        )
        .first()
    )


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    review = _normalize_resolutions(resolutions)
    result: list[dict[str, Any]] = []
    for record in records:
        source, _ = _source_record(record)
        source_id = _positive_id(record.get("Id"))
        if source is None:
            result.append({"source_id": source_id, "dependencies": None, "reviewed_target": None})
            continue
        deps = {}
        for key, resource, source_key, entity in (
            ("source_bank", "BANK_ACCOUNTS", "source_bank_source_id", "BANK_ACCOUNT"),
            ("destination_bank", "BANK_ACCOUNTS", "destination_bank_source_id", "BANK_ACCOUNT"),
            ("property", "PROPERTIES", "property_source_id", "PROPERTY"),
            ("unit", "UNITS", "unit_source_id", "UNIT"),
        ):
            mapped = _dependency(
                db,
                run=run,
                resource=resource,
                source_id=source[source_key],
                target_entity=entity,
            )
            deps[key] = (
                {"target_id": mapped.target_id, "source_fingerprint": mapped.source_fingerprint}
                if mapped is not None
                else None
            )
        reviewed_target = None
        resolution = review.get(source["source_id"])
        if resolution and resolution["action"] == "MATCH_EXISTING":
            target = (
                db.query(GLTransaction)
                .filter(
                    GLTransaction.id == resolution["target_gl_transaction_id"],
                    GLTransaction.organization_id == run.organization_id,
                )
                .first()
            )
            if target is not None:
                reviewed_target = {
                    "id": target.id,
                    "transaction_date": target.transaction_date.isoformat(),
                    "transaction_type": target.transaction_type,
                    "is_reversed": bool(target.is_reversed),
                    "reversal_of_id": target.reversal_of_id,
                    "entries": [
                        {
                            "gl_account_id": entry.gl_account_id,
                            "property_id": entry.property_id,
                            "unit_id": entry.unit_id,
                            "owner_id": entry.owner_id,
                            "debit": f"{Decimal(entry.debit or 0).quantize(CENT):.2f}",
                            "credit": f"{Decimal(entry.credit or 0).quantize(CENT):.2f}",
                        }
                        for entry in sorted(target.entries, key=lambda row: row.id)
                    ],
                }
        result.append(
            {"source_id": source["source_id"], "dependencies": deps, "reviewed_target": reviewed_target}
        )
    return result


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    review = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "BANK_TRANSFERS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "dependencies": _dependency_snapshot(
            db, run=run, records=records, resolutions=resolutions
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _resolved_dependencies(
    db: Session, *, run: PlatformMigrationRun, source: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    source_bank_mapping = _dependency(
        db, run=run, resource="BANK_ACCOUNTS",
        source_id=source["source_bank_source_id"], target_entity="BANK_ACCOUNT",
    )
    destination_bank_mapping = _dependency(
        db, run=run, resource="BANK_ACCOUNTS",
        source_id=source["destination_bank_source_id"], target_entity="BANK_ACCOUNT",
    )
    property_mapping = _dependency(
        db, run=run, resource="PROPERTIES",
        source_id=source["property_source_id"], target_entity="PROPERTY",
    )
    unit_mapping = _dependency(
        db, run=run, resource="UNITS",
        source_id=source["unit_source_id"], target_entity="UNIT",
    )
    if source_bank_mapping is None or destination_bank_mapping is None:
        return None, "Bank Transfer migration requires durable same-run mappings for both Buildium Bank Accounts."
    if property_mapping is None:
        return None, "Bank Transfer migration requires a durable same-run Buildium Property mapping."
    if source["unit_source_id"] is not None and unit_mapping is None:
        return None, "Bank Transfer migration requires a durable same-run Buildium Unit mapping when Unit is supplied."

    source_bank = _target_bank(db, run=run, target_id=source_bank_mapping.target_id)
    destination_bank = _target_bank(db, run=run, target_id=destination_bank_mapping.target_id)
    target_property = _target_property(db, run=run, target_id=property_mapping.target_id)
    target_unit = None
    if unit_mapping is not None:
        target_unit = _target_unit(
            db, run=run, target_id=unit_mapping.target_id,
            property_id=property_mapping.target_id,
        )
    if source_bank is None or destination_bank is None:
        return None, "Mapped source or destination Bank Account is no longer active in the target organization."
    if source_bank.id == destination_bank.id:
        return None, "Source and destination Bank Account mappings resolve to the same target account."
    if source_bank.gl_account_id == destination_bank.gl_account_id:
        return None, "Source and destination Bank Account mappings resolve to the same target GL account."
    if target_property is None:
        return None, "Mapped Property is no longer active in the target organization."
    if unit_mapping is not None and target_unit is None:
        return None, "Mapped Unit is no longer active under the mapped Property."
    return {
        "source_bank": source_bank,
        "destination_bank": destination_bank,
        "property": target_property,
        "unit": target_unit,
    }, None


def _matches_target(
    target: GLTransaction, *, source: dict[str, Any], deps: dict[str, Any]
) -> bool:
    if (
        target.organization_id != deps["property"].organization_id
        or target.transaction_type != "TRANSFER"
        or target.transaction_date != source["entry_date"]
        or bool(target.is_reversed)
        or target.reversal_of_id is not None
    ):
        return False
    entries = list(target.entries)
    if len(entries) != 2:
        return False
    property_id = deps["property"].id
    unit_id = deps["unit"].id if deps["unit"] is not None else None
    expected = {
        (
            deps["source_bank"].gl_account_id, property_id, unit_id, None,
            Decimal("0.00"), source["amount"],
        ),
        (
            deps["destination_bank"].gl_account_id, property_id, unit_id, None,
            source["amount"], Decimal("0.00"),
        ),
    }
    actual = set()
    for entry in entries:
        if entry.organization_id != target.organization_id:
            return False
        actual.add(
            (
                entry.gl_account_id, entry.property_id, entry.unit_id, entry.owner_id,
                Decimal(entry.debit or 0).quantize(CENT),
                Decimal(entry.credit or 0).quantize(CENT),
            )
        )
    return actual == expected


def dry_run_bank_transfers(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> BankTransferDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumBankTransferMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumBankTransferMigrationError(
            "At least one Buildium Bank Transfer record is required."
        )
    review = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        source, reason = _source_record(record)
        source_id = _positive_id(record.get("Id"))
        if source_id and source_id in seen:
            rows.append({
                "source_id": source_id, "reviewable": False,
                "reason": "Duplicate Buildium Bank Transfer Id in this dry run.",
                "mapped": None, "warnings": [], "resolution_action": None,
                "resolution_target_gl_transaction_id": None,
            })
            invalid += 1
            continue
        if source_id:
            seen.add(source_id)
        if source is None:
            rows.append({
                "source_id": source_id, "reviewable": False, "reason": reason,
                "mapped": None, "warnings": [], "resolution_action": None,
                "resolution_target_gl_transaction_id": None,
            })
            invalid += 1
            continue

        deps, dependency_error = _resolved_dependencies(db, run=run, source=source)
        if deps is None:
            rows.append({
                "source_id": source["source_id"], "reviewable": False,
                "reason": dependency_error, "mapped": None, "warnings": [],
                "resolution_action": None, "resolution_target_gl_transaction_id": None,
            })
            invalid += 1
            continue

        valid_ids.add(source["source_id"])
        resolution = review.get(source["source_id"])
        prior = _mapping(
            db, run=run, resource="BANK_TRANSFERS",
            source_id=source["source_id"],
            target_entity="GL_TRANSACTION_TRANSFER_RELATIONSHIP",
        )
        warnings = [
            "This batch reconciles only the documented Rental bank-transfer subset to an already-existing target TRANSFER transaction.",
            "SourceBankAccountId is retrieval-path context supplied alongside the Buildium transfer response; it is fingerprint-bound.",
            "No bank account, GL transaction, GL entry, balance, cleared state, or reconciliation history is created or changed.",
            "Association and Company accounting entities remain blocked in this bounded batch.",
        ]
        action = resolution["action"] if resolution else None
        target_id = resolution["target_gl_transaction_id"] if resolution else None

        if prior is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != prior.target_id
            ):
                raise BuildiumBankTransferMigrationError(
                    f"Buildium Bank Transfer source ID {source['source_id']} is already mapped and cannot be re-resolved."
                )
            target = db.query(GLTransaction).filter(
                GLTransaction.id == prior.target_id,
                GLTransaction.organization_id == run.organization_id,
            ).first()
            if target is None or not _matches_target(target, source=source, deps=deps):
                rows.append({
                    "source_id": source["source_id"], "reviewable": False,
                    "reason": "Previously mapped target transfer no longer matches the reviewed source contract.",
                    "mapped": None, "warnings": warnings, "resolution_action": None,
                    "resolution_target_gl_transaction_id": None,
                })
                invalid += 1
                warning_count += len(warnings)
                continue
            action = "ALREADY_MAPPED"
            target_id = prior.target_id
            warnings.append(
                f"Buildium Bank Transfer is already durably mapped to local GL transaction #{prior.target_id}; commit will replay."
            )

        if action == "SKIP":
            rows.append({
                "source_id": source["source_id"], "reviewable": False,
                "reason": "Explicitly skipped after Buildium Bank Transfer review.",
                "mapped": None, "warnings": warnings, "resolution_action": "SKIP",
                "resolution_target_gl_transaction_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue

        if action == "MATCH_EXISTING":
            target = db.query(GLTransaction).filter(
                GLTransaction.id == target_id,
                GLTransaction.organization_id == run.organization_id,
            ).first()
            if target is None:
                raise BuildiumBankTransferMigrationError(
                    f"Reviewed target GL transaction #{target_id} is not in the target organization."
                )
            if not _matches_target(target, source=source, deps=deps):
                raise BuildiumBankTransferMigrationError(
                    "Reviewed target GL transfer no longer matches the Buildium banks, date, amount, or Rental property/unit contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local GL transaction #{target.id}; commit creates migration metadata only."
            )
        elif action is None:
            candidates = (
                db.query(GLTransaction)
                .filter(
                    GLTransaction.organization_id == run.organization_id,
                    GLTransaction.transaction_type == "TRANSFER",
                    GLTransaction.transaction_date == source["entry_date"],
                    GLTransaction.is_reversed.is_(False),
                    GLTransaction.reversal_of_id.is_(None),
                )
                .order_by(GLTransaction.id.asc()).limit(25).all()
            )
            exact = [
                candidate for candidate in candidates
                if _matches_target(candidate, source=source, deps=deps)
            ]
            if len(exact) == 1:
                warnings.append(
                    f"Possible exact existing target GL transfer #{exact[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(exact) > 1:
                warnings.append("Multiple exact target GL transfers exist; no candidate is auto-selected.")
            else:
                warnings.append("No exact existing target GL transfer matches; this batch does not create one.")

        rows.append({
            "source_id": source["source_id"], "reviewable": True, "reason": None,
            "mapped": {
                "source_target_bank_account_id": deps["source_bank"].id,
                "destination_target_bank_account_id": deps["destination_bank"].id,
                "target_property_id": deps["property"].id,
                "target_unit_id": deps["unit"].id if deps["unit"] is not None else None,
                "entry_date": source["entry_date"].isoformat(),
                "total_amount": f"{source['amount']:.2f}",
                "target_gl_transaction_id": target_id,
            },
            "warnings": warnings, "resolution_action": action,
            "resolution_target_gl_transaction_id": target_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(review) - valid_ids, key=int)
    if unknown:
        raise BuildiumBankTransferMigrationError(
            "Bank Transfer review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BANK_TRANSFERS",
        "transport": "BUILDIUM_API_V1_RECORDS_PLUS_PATH_CONTEXT",
        "total": len(records), "reviewable": reviewable,
        "skipped_review": skipped, "invalid": invalid, "warning_count": warning_count,
        "target_transfers_created": False, "gl_history_created": False,
        "bank_balances_changed": False, "clearing_state_changed": False,
        "raw_payload_stored": False, "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "BANK_TRANSFERS_DRY_RUN_READY"
        db.flush()
    return BankTransferDryRunResult(
        fingerprint=fingerprint, replayed=replayed, total=len(records),
        reviewable=reviewable, skipped_review=skipped, invalid=invalid,
        warning_count=warning_count, rows=rows, summary=summary,
    )


def commit_bank_transfers(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> BankTransferCommitResult:
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if fingerprint != expected_fingerprint:
        raise BuildiumBankTransferMigrationError(
            "Buildium Bank Transfer dry run is stale; review again before commit."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumBankTransferMigrationError(
            "Commit requires the exact latest Buildium Bank Transfer dry run."
        )
    preview = dry_run_bank_transfers(db, run=run, records=records, resolutions=resolutions)
    if preview.invalid:
        raise BuildiumBankTransferMigrationError(
            "Buildium Bank Transfer commit is blocked while invalid records remain."
        )
    review = _normalize_resolutions(resolutions)
    unresolved = [row["source_id"] for row in preview.rows if row["resolution_action"] is None]
    if unresolved:
        raise BuildiumBankTransferMigrationError(
            "Bank Transfer migration requires explicit review for source IDs: "
            + ", ".join(unresolved)
        )

    rows: list[dict[str, Any]] = []
    matched = skipped = 0
    changed = False
    review_recorded = False
    by_id = {
        _positive_id(record.get("Id")): record
        for record in records
        if _positive_id(record.get("Id")) is not None
    }
    for row in preview.rows:
        source_id = row["source_id"]
        prior = _mapping(
            db, run=run, resource="BANK_TRANSFERS", source_id=source_id,
            target_entity="GL_TRANSACTION_TRANSFER_RELATIONSHIP",
        )
        if prior is not None:
            rows.append({
                "source_id": source_id,
                "target_gl_transaction_id": prior.target_id,
                "replayed": True,
            })
            continue
        resolution = review[source_id]
        if resolution["action"] == "SKIP":
            skipped += 1
            continue
        source, reason = _source_record(by_id[source_id])
        if source is None:
            raise BuildiumBankTransferMigrationError(reason or "Invalid source record.")
        deps, dependency_error = _resolved_dependencies(db, run=run, source=source)
        target = db.query(GLTransaction).filter(
            GLTransaction.id == resolution["target_gl_transaction_id"],
            GLTransaction.organization_id == run.organization_id,
        ).first()
        if deps is None or target is None or not _matches_target(target, source=source, deps=deps):
            raise BuildiumBankTransferMigrationError(
                dependency_error or "Reviewed target GL transfer changed after dry run."
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id, organization_id=run.organization_id,
                provider="BUILDIUM", resource="BANK_TRANSFERS", source_id=source_id,
                target_entity="GL_TRANSACTION_TRANSFER_RELATIONSHIP",
                target_id=target.id, source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_id": source_id, "target_gl_transaction_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True
    if changed:
        run.status = "BANK_TRANSFERS_RECONCILED"
        db.flush()
    elif skipped and not rows:
        run.status = "BANK_TRANSFERS_REVIEWED"
        db.flush()
        review_recorded = True
    return BankTransferCommitResult(
        fingerprint=fingerprint, replayed=not changed and not review_recorded,
        matched_existing=matched, skipped_review=skipped,
        warning_count=preview.warning_count, rows=rows,
    )
