"""Buildium bank-withdrawal existing-target reconciliation for Phase 4.14.

Consumes the documented Buildium bank withdrawal shape plus source-bank path
context. This bounded batch supports only Company-scoped withdrawals that can
be proven to equal an already-existing target BANK_ADJUSTMENT decrease.
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
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun


class BuildiumBankWithdrawalMigrationError(ValueError):
    pass


CENT = Decimal("0.01")
MAX_ABS_MONEY = Decimal("999999999999.99")


@dataclass(frozen=True)
class BankWithdrawalDryRunResult:
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
class BankWithdrawalCommitResult:
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
        raise BuildiumBankWithdrawalMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _source_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    source_bank_id = _positive_id(record.get("SourceBankAccountId"))
    offset_gl_id = _positive_id(record.get("OffsetGLAccountId"))
    entry_date, date_error = _date_value(record.get("EntryDate"))
    amount, amount_error = _money(record.get("TotalAmount"))

    entity = record.get("AccountingEntity")
    if not isinstance(entity, dict):
        return None, "AccountingEntity must contain the documented Buildium withdrawal accounting entity."
    entity_type = _clean(entity.get("AccountingEntityType"))
    company_source_id = _positive_id(entity.get("Id"))

    errors = [
        item
        for item in (
            None if source_id is not None else "Buildium withdrawal Id must be a positive integer.",
            None if source_bank_id is not None else "SourceBankAccountId retrieval context must be a positive integer.",
            None if offset_gl_id is not None else "OffsetGLAccountId must be a positive integer.",
            date_error,
            amount_error,
            None if entity_type == "Company" else "This bounded batch supports only Buildium Company bank withdrawals.",
            None if company_source_id is not None else "Company AccountingEntity.Id must be a positive Buildium Company Id.",
        )
        if item
    ]
    if errors:
        return None, " ".join(errors)

    return {
        "source_id": source_id,
        "source_bank_source_id": source_bank_id,
        "offset_gl_source_id": offset_gl_id,
        "company_source_id": company_source_id,
        "entry_date": entry_date,
        "amount": amount,
    }, None


def _normalize_resolutions(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumBankWithdrawalMigrationError(
                "Bank Withdrawal review requires unique positive source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBankWithdrawalMigrationError(
                "Bank Withdrawal review supports only MATCH_EXISTING or SKIP."
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
                raise BuildiumBankWithdrawalMigrationError(
                    "MATCH_EXISTING requires a positive target_gl_transaction_id."
                )
        elif target_id is not None:
            raise BuildiumBankWithdrawalMigrationError(
                "target_gl_transaction_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_gl_transaction_id": target_id,
        }
    return result


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


def _resolved_dependencies(
    db: Session, *, run: PlatformMigrationRun, source: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    bank_mapping = _mapping(
        db, run=run, resource="BANK_ACCOUNTS",
        source_id=source["source_bank_source_id"], target_entity="BANK_ACCOUNT",
    )
    offset_mapping = _mapping(
        db, run=run, resource="GL_ACCOUNTS",
        source_id=source["offset_gl_source_id"], target_entity="GL_ACCOUNT",
    )
    if bank_mapping is None:
        return None, "Bank Withdrawal migration requires a durable same-run Buildium Bank Account mapping."
    if offset_mapping is None:
        return None, "Bank Withdrawal migration requires a durable same-run Buildium Offset GL Account mapping."

    bank = _target_bank(db, run=run, target_id=bank_mapping.target_id)
    offset = _target_gl(db, run=run, target_id=offset_mapping.target_id)
    if bank is None:
        return None, "Mapped Bank Account is no longer active in the target organization."
    if offset is None:
        return None, "Mapped Offset GL Account is no longer active in the target organization."
    if bank.gl_account_id == offset.id:
        return None, "Mapped Offset GL Account must differ from the Bank Account GL account."
    return {"bank": bank, "offset": offset, "bank_mapping": bank_mapping, "offset_mapping": offset_mapping}, None


def _target_snapshot(target: GLTransaction | None) -> dict[str, Any] | None:
    if target is None:
        return None
    return {
        "id": target.id,
        "transaction_date": target.transaction_date.isoformat(),
        "transaction_type": target.transaction_type,
        "source_type": target.source_type,
        "source_id": target.source_id,
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
        deps, _ = _resolved_dependencies(db, run=run, source=source)
        dependency_data = None
        if deps is not None:
            dependency_data = {
                "bank": {
                    "target_id": deps["bank_mapping"].target_id,
                    "source_fingerprint": deps["bank_mapping"].source_fingerprint,
                },
                "offset_gl": {
                    "target_id": deps["offset_mapping"].target_id,
                    "source_fingerprint": deps["offset_mapping"].source_fingerprint,
                },
            }
        reviewed_target = None
        resolution = review.get(source["source_id"])
        if resolution and resolution["action"] == "MATCH_EXISTING":
            reviewed_target = _target_snapshot(
                db.query(GLTransaction).filter(
                    GLTransaction.id == resolution["target_gl_transaction_id"],
                    GLTransaction.organization_id == run.organization_id,
                ).first()
            )
        result.append({
            "source_id": source["source_id"],
            "dependencies": dependency_data,
            "reviewed_target": reviewed_target,
        })
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
        "resource": "BANK_WITHDRAWALS",
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


def _matches_target(
    target: GLTransaction, *, source: dict[str, Any], deps: dict[str, Any]
) -> bool:
    bank = deps["bank"]
    offset = deps["offset"]
    if (
        target.organization_id != bank.organization_id
        or target.transaction_type != "BANK_ADJUSTMENT"
        or target.source_type != "bank_adjustment"
        or target.source_id != bank.id
        or target.transaction_date != source["entry_date"]
        or bool(target.is_reversed)
        or target.reversal_of_id is not None
    ):
        return False
    entries = list(target.entries)
    if len(entries) != 2:
        return False
    expected = {
        (offset.id, None, None, None, source["amount"], Decimal("0.00")),
        (bank.gl_account_id, None, None, None, Decimal("0.00"), source["amount"]),
    }
    actual = {
        (
            entry.gl_account_id,
            entry.property_id,
            entry.unit_id,
            entry.owner_id,
            Decimal(entry.debit or 0).quantize(CENT),
            Decimal(entry.credit or 0).quantize(CENT),
        )
        for entry in entries
        if entry.organization_id == target.organization_id
    }
    return len(actual) == 2 and actual == expected


def dry_run_bank_withdrawals(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> BankWithdrawalDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumBankWithdrawalMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumBankWithdrawalMigrationError(
            "At least one Buildium Bank Withdrawal record is required."
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
                "reason": "Duplicate Buildium Bank Withdrawal Id in this dry run.",
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
            db, run=run, resource="BANK_WITHDRAWALS",
            source_id=source["source_id"],
            target_entity="GL_TRANSACTION_BANK_ADJUSTMENT_RELATIONSHIP",
        )
        warnings = [
            "This batch reconciles only the documented Company-scoped Buildium withdrawal subset to an already-existing target BANK_ADJUSTMENT decrease.",
            "SourceBankAccountId is retrieval-path context supplied alongside the Buildium withdrawal response and is fingerprint-bound.",
            "Rental and Association withdrawal scopes remain blocked because the target Bank Adjustment contract does not preserve those entity tags.",
            "No bank account, GL transaction, GL entry, balance, cleared state, or reconciliation history is created or changed.",
        ]
        action = resolution["action"] if resolution else None
        target_id = resolution["target_gl_transaction_id"] if resolution else None

        if prior is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != prior.target_id
            ):
                raise BuildiumBankWithdrawalMigrationError(
                    f"Buildium Bank Withdrawal source ID {source['source_id']} is already mapped and cannot be re-resolved."
                )
            target = db.query(GLTransaction).filter(
                GLTransaction.id == prior.target_id,
                GLTransaction.organization_id == run.organization_id,
            ).first()
            if target is None or not _matches_target(target, source=source, deps=deps):
                rows.append({
                    "source_id": source["source_id"], "reviewable": False,
                    "reason": "Previously mapped target bank adjustment no longer matches the reviewed withdrawal contract.",
                    "mapped": None, "warnings": warnings, "resolution_action": None,
                    "resolution_target_gl_transaction_id": None,
                })
                invalid += 1
                warning_count += len(warnings)
                continue
            action = "ALREADY_MAPPED"
            target_id = prior.target_id
            warnings.append(
                f"Buildium Bank Withdrawal is already durably mapped to local GL transaction #{prior.target_id}; commit will replay."
            )

        if action == "SKIP":
            rows.append({
                "source_id": source["source_id"], "reviewable": False,
                "reason": "Explicitly skipped after Buildium Bank Withdrawal review.",
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
                raise BuildiumBankWithdrawalMigrationError(
                    f"Reviewed target GL transaction #{target_id} is not in the target organization."
                )
            if not _matches_target(target, source=source, deps=deps):
                raise BuildiumBankWithdrawalMigrationError(
                    "Reviewed target bank adjustment no longer matches the Buildium bank, offset GL, date, amount, or Company scope contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local GL transaction #{target.id}; commit creates migration metadata only."
            )
        elif action is None:
            candidates = (
                db.query(GLTransaction)
                .filter(
                    GLTransaction.organization_id == run.organization_id,
                    GLTransaction.transaction_type == "BANK_ADJUSTMENT",
                    GLTransaction.source_type == "bank_adjustment",
                    GLTransaction.source_id == deps["bank"].id,
                    GLTransaction.transaction_date == source["entry_date"],
                    GLTransaction.is_reversed.is_(False),
                    GLTransaction.reversal_of_id.is_(None),
                )
                .order_by(GLTransaction.id.asc()).limit(25).all()
            )
            exact = [candidate for candidate in candidates if _matches_target(candidate, source=source, deps=deps)]
            if len(exact) == 1:
                warnings.append(
                    f"Possible exact existing target bank adjustment #{exact[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(exact) > 1:
                warnings.append("Multiple exact target bank adjustments exist; no candidate is auto-selected.")
            else:
                warnings.append("No exact existing target bank adjustment matches; this batch does not create one.")

        rows.append({
            "source_id": source["source_id"], "reviewable": True, "reason": None,
            "mapped": {
                "source_target_bank_account_id": deps["bank"].id,
                "target_offset_gl_account_id": deps["offset"].id,
                "source_company_id": int(source["company_source_id"]),
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
        raise BuildiumBankWithdrawalMigrationError(
            "Bank Withdrawal review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BANK_WITHDRAWALS",
        "transport": "BUILDIUM_API_V1_RECORDS_PLUS_PATH_CONTEXT",
        "total": len(records), "reviewable": reviewable,
        "skipped_review": skipped, "invalid": invalid, "warning_count": warning_count,
        "target_adjustments_created": False, "gl_history_created": False,
        "bank_balances_changed": False, "clearing_state_changed": False,
        "raw_payload_stored": False, "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "BANK_WITHDRAWALS_DRY_RUN_READY"
        db.flush()
    return BankWithdrawalDryRunResult(
        fingerprint=fingerprint, replayed=replayed, total=len(records),
        reviewable=reviewable, skipped_review=skipped, invalid=invalid,
        warning_count=warning_count, rows=rows, summary=summary,
    )


def commit_bank_withdrawals(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> BankWithdrawalCommitResult:
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if fingerprint != expected_fingerprint:
        raise BuildiumBankWithdrawalMigrationError(
            "Buildium Bank Withdrawal dry run is stale; review again before commit."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumBankWithdrawalMigrationError(
            "Commit requires the exact latest Buildium Bank Withdrawal dry run."
        )
    preview = dry_run_bank_withdrawals(db, run=run, records=records, resolutions=resolutions)
    if preview.invalid:
        raise BuildiumBankWithdrawalMigrationError(
            "Buildium Bank Withdrawal commit is blocked while invalid records remain."
        )
    review = _normalize_resolutions(resolutions)
    unresolved = [row["source_id"] for row in preview.rows if row["resolution_action"] is None]
    if unresolved:
        raise BuildiumBankWithdrawalMigrationError(
            "Bank Withdrawal migration requires explicit review for source IDs: "
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
            db, run=run, resource="BANK_WITHDRAWALS", source_id=source_id,
            target_entity="GL_TRANSACTION_BANK_ADJUSTMENT_RELATIONSHIP",
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
            raise BuildiumBankWithdrawalMigrationError(reason or "Invalid source record.")
        deps, dependency_error = _resolved_dependencies(db, run=run, source=source)
        target = db.query(GLTransaction).filter(
            GLTransaction.id == resolution["target_gl_transaction_id"],
            GLTransaction.organization_id == run.organization_id,
        ).first()
        if deps is None or target is None or not _matches_target(target, source=source, deps=deps):
            raise BuildiumBankWithdrawalMigrationError(
                dependency_error or "Reviewed target bank adjustment changed after dry run."
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id, organization_id=run.organization_id,
                provider="BUILDIUM", resource="BANK_WITHDRAWALS", source_id=source_id,
                target_entity="GL_TRANSACTION_BANK_ADJUSTMENT_RELATIONSHIP",
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
        run.status = "BANK_WITHDRAWALS_RECONCILED"
        db.flush()
    elif skipped and not rows:
        run.status = "BANK_WITHDRAWALS_REVIEWED"
        db.flush()
        review_recorded = True
    return BankWithdrawalCommitResult(
        fingerprint=fingerprint, replayed=not changed and not review_recorded,
        matched_existing=matched, skipped_review=skipped,
        warning_count=preview.warning_count, rows=rows,
    )
