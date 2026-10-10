"""Buildium bank-reconciliation existing-target reconciliation for Phase 4.14.

This bounded adapter consumes Buildium reconciliation identity plus the documented
balance response and maps only to an already-existing target BankReconciliation.
It never changes cleared selections, statement lines, reconciliation state, bank
balances, GL transactions, or customer accounting history.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.bank_reconciliation import BankReconciliation
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.services.bank_reconciliation import cleared_balance, difference


class BuildiumBankReconciliationMigrationError(ValueError):
    pass


CENT = Decimal("0.01")
MAX_ABS_MONEY = Decimal("999999999999.99")


@dataclass(frozen=True)
class BankReconciliationDryRunResult:
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
class BankReconciliationCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


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
        return None, f"{field} is required."
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None, f"{field} must be a finite monetary amount."
    if not amount.is_finite() or abs(amount) > MAX_ABS_MONEY:
        return None, f"{field} must be a finite monetary amount."
    normalized = amount.quantize(CENT)
    if normalized != amount:
        return None, f"{field} must have no more than two decimal places."
    return normalized, None


def _date_value(value: Any) -> tuple[date | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return None, "StatementEndingDate is required."
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, "StatementEndingDate must be an ISO date (YYYY-MM-DD)."


def _boolean(value: Any) -> tuple[bool | None, str | None]:
    if isinstance(value, bool):
        return value, None
    return None, "IsFinished must be a boolean."


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
        raise BuildiumBankReconciliationMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _source_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    bank_source_id = _positive_id(record.get("BankAccountId"))
    finished, finished_error = _boolean(record.get("IsFinished"))
    statement_date, date_error = _date_value(record.get("StatementEndingDate"))

    balance = record.get("Balance")
    if not isinstance(balance, dict):
        return None, "Balance must contain the documented Buildium reconciliation balance response."
    statement = balance.get("StatementBalance")
    cleared = balance.get("ClearedBalance")
    if not isinstance(statement, dict) or not isinstance(cleared, dict):
        return None, "Balance must include StatementBalance and ClearedBalance objects."

    beginning, beginning_error = _money(
        statement.get("BeginningBalance"), field="StatementBalance.BeginningBalance"
    )
    ending, ending_error = _money(
        statement.get("EndingBalance"), field="StatementBalance.EndingBalance"
    )
    cleared_ending, cleared_error = _money(
        cleared.get("EndingBalance"), field="ClearedBalance.EndingBalance"
    )
    source_difference, difference_error = _money(
        balance.get("Difference"), field="Balance.Difference"
    )

    errors = [
        item
        for item in (
            None if source_id is not None else "Buildium reconciliation Id must be a positive integer.",
            None if bank_source_id is not None else "BankAccountId must be a positive integer.",
            finished_error,
            date_error,
            beginning_error,
            ending_error,
            cleared_error,
            difference_error,
        )
        if item
    ]
    if errors:
        return None, " ".join(errors)
    return {
        "source_id": source_id,
        "bank_source_id": bank_source_id,
        "is_finished": finished,
        "statement_date": statement_date,
        "beginning_balance": beginning,
        "ending_balance": ending,
        "cleared_ending_balance": cleared_ending,
        "difference": source_difference,
    }, None


def _normalize_resolutions(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumBankReconciliationMigrationError(
                "Bank Reconciliation review requires unique positive source_id values."
            )
        action = str(item.get("action") or "").strip()
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBankReconciliationMigrationError(
                "Bank Reconciliation review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_reconciliation_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumBankReconciliationMigrationError(
                    "MATCH_EXISTING requires a positive target_reconciliation_id."
                )
        elif target_id is not None:
            raise BuildiumBankReconciliationMigrationError(
                "target_reconciliation_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_reconciliation_id": target_id,
        }
    return result


def _bank_dependency(
    db: Session,
    *,
    run: PlatformMigrationRun,
    source_id: str,
) -> PlatformMigrationItem | None:
    return _mapping(
        db,
        run=run,
        resource="BANK_ACCOUNTS",
        source_id=source_id,
        target_entity="BANK_ACCOUNT",
    )


def _target_reconciliation(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> BankReconciliation | None:
    return (
        db.query(BankReconciliation)
        .filter(
            BankReconciliation.id == target_id,
            BankReconciliation.organization_id == run.organization_id,
        )
        .first()
    )


def _target_snapshot(target: BankReconciliation | None) -> dict[str, Any] | None:
    if target is None:
        return None
    return {
        "id": target.id,
        "bank_account_id": target.bank_account_id,
        "statement_date": target.statement_date.isoformat(),
        "beginning_balance": f"{Decimal(target.beginning_balance or 0).quantize(CENT):.2f}",
        "ending_statement_balance": f"{Decimal(target.ending_statement_balance or 0).quantize(CENT):.2f}",
        "status": target.status,
        "cleared_balance": f"{cleared_balance(target):.2f}",
        "difference": f"{difference(target):.2f}",
    }


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    review = _normalize_resolutions(resolutions)
    dependencies: list[dict[str, Any]] = []
    for record in records:
        source_id = _positive_id(record.get("Id"))
        bank_source_id = _positive_id(record.get("BankAccountId"))
        bank_mapping = (
            _bank_dependency(db, run=run, source_id=bank_source_id)
            if bank_source_id
            else None
        )
        resolution = review.get(source_id or "")
        target = None
        if resolution and resolution["action"] == "MATCH_EXISTING":
            target = _target_reconciliation(
                db,
                run=run,
                target_id=resolution["target_reconciliation_id"],
            )
        dependencies.append(
            {
                "source_id": source_id,
                "bank_source_id": bank_source_id,
                "bank_mapping_target_id": bank_mapping.target_id if bank_mapping else None,
                "bank_mapping_source_fingerprint": (
                    bank_mapping.source_fingerprint if bank_mapping else None
                ),
                "reviewed_target": _target_snapshot(target),
            }
        )
    payload = {
        "provider": "BUILDIUM",
        "resource": "BANK_RECONCILIATIONS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "dependencies": dependencies,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _matches_source(
    target: BankReconciliation,
    source: dict[str, Any],
    bank_target_id: int,
) -> bool:
    expected_status = "RECONCILED" if source["is_finished"] else "OPEN"
    return (
        target.bank_account_id == bank_target_id
        and target.statement_date == source["statement_date"]
        and Decimal(target.beginning_balance or 0).quantize(CENT) == source["beginning_balance"]
        and Decimal(target.ending_statement_balance or 0).quantize(CENT) == source["ending_balance"]
        and target.status == expected_status
        and cleared_balance(target) == source["cleared_ending_balance"]
        and difference(target) == source["difference"]
    )


def dry_run_bank_reconciliations(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> BankReconciliationDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumBankReconciliationMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumBankReconciliationMigrationError(
            "At least one Buildium Bank Reconciliation record is required."
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
                "source_id": source_id,
                "reviewable": False,
                "reason": "Duplicate Buildium reconciliation Id in this dry run.",
                "mapped": None,
                "warnings": [],
                "resolution_action": None,
                "resolution_target_reconciliation_id": None,
            })
            invalid += 1
            continue
        if source_id:
            seen.add(source_id)
        if source is None:
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": reason,
                "mapped": None,
                "warnings": [],
                "resolution_action": None,
                "resolution_target_reconciliation_id": None,
            })
            invalid += 1
            continue

        bank_mapping = _bank_dependency(
            db, run=run, source_id=source["bank_source_id"]
        )
        if bank_mapping is None:
            rows.append({
                "source_id": source["source_id"],
                "reviewable": False,
                "reason": (
                    "Bank Reconciliation migration requires a durable same-run "
                    "Buildium Bank Account mapping."
                ),
                "mapped": None,
                "warnings": [],
                "resolution_action": None,
                "resolution_target_reconciliation_id": None,
            })
            invalid += 1
            continue

        valid_ids.add(source["source_id"])
        resolution = review.get(source["source_id"])
        prior = _mapping(
            db,
            run=run,
            resource="BANK_RECONCILIATIONS",
            source_id=source["source_id"],
            target_entity="BANK_RECONCILIATION",
        )
        warnings = [
            "This batch maps Buildium reconciliation identity and documented balances to an already-existing target reconciliation only.",
            "It never changes cleared selections, statement lines, reconciliation status, bank balances, or GL history.",
            "Buildium reconciliation transaction identities are not imported or marked cleared by this batch.",
        ]
        action = resolution["action"] if resolution else None
        target_id = resolution["target_reconciliation_id"] if resolution else None

        if prior is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != prior.target_id
            ):
                raise BuildiumBankReconciliationMigrationError(
                    f"Buildium reconciliation source ID {source['source_id']} is already mapped and cannot be re-resolved."
                )
            target = _target_reconciliation(db, run=run, target_id=prior.target_id)
            if target is None or not _matches_source(target, source, bank_mapping.target_id):
                rows.append({
                    "source_id": source["source_id"],
                    "reviewable": False,
                    "reason": "Previously mapped target reconciliation no longer matches the reviewed source contract.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": None,
                    "resolution_target_reconciliation_id": None,
                })
                invalid += 1
                warning_count += len(warnings)
                continue
            action = "ALREADY_MAPPED"
            target_id = prior.target_id
            warnings.append(
                f"Buildium reconciliation is already durably mapped to local reconciliation #{prior.target_id}; commit will replay."
            )

        if action == "SKIP":
            rows.append({
                "source_id": source["source_id"],
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Bank Reconciliation review.",
                "mapped": None,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_reconciliation_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue

        if action == "MATCH_EXISTING":
            target = _target_reconciliation(db, run=run, target_id=target_id)
            if target is None:
                raise BuildiumBankReconciliationMigrationError(
                    f"Reviewed target reconciliation #{target_id} is not in the target organization."
                )
            if not _matches_source(target, source, bank_mapping.target_id):
                raise BuildiumBankReconciliationMigrationError(
                    "Reviewed target reconciliation no longer matches the Buildium bank, statement date, status, or balance contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local reconciliation #{target.id}; commit creates migration metadata only."
            )
        elif action is None:
            candidates = (
                db.query(BankReconciliation)
                .filter(
                    BankReconciliation.organization_id == run.organization_id,
                    BankReconciliation.bank_account_id == bank_mapping.target_id,
                    BankReconciliation.statement_date == source["statement_date"],
                    BankReconciliation.status == (
                        "RECONCILED" if source["is_finished"] else "OPEN"
                    ),
                )
                .order_by(BankReconciliation.id.asc())
                .limit(5)
                .all()
            )
            exact = [
                candidate
                for candidate in candidates
                if _matches_source(candidate, source, bank_mapping.target_id)
            ]
            if len(exact) == 1:
                warnings.append(
                    f"Possible exact existing target reconciliation #{exact[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(exact) > 1:
                warnings.append(
                    "Multiple exact target reconciliations exist; no candidate is auto-selected."
                )
            else:
                warnings.append(
                    "No exact existing target reconciliation matches; this batch does not create one."
                )

        mapped = {
            "target_bank_account_id": bank_mapping.target_id,
            "statement_ending_date": source["statement_date"].isoformat(),
            "is_finished": source["is_finished"],
            "statement_beginning_balance": f"{source['beginning_balance']:.2f}",
            "statement_ending_balance": f"{source['ending_balance']:.2f}",
            "cleared_ending_balance": f"{source['cleared_ending_balance']:.2f}",
            "difference": f"{source['difference']:.2f}",
            "target_reconciliation_id": target_id,
            "bank_mapping_source_fingerprint": bank_mapping.source_fingerprint,
        }
        rows.append({
            "source_id": source["source_id"],
            "reviewable": True,
            "reason": None,
            "mapped": mapped,
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_reconciliation_id": target_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(review) - valid_ids, key=int)
    if unknown:
        raise BuildiumBankReconciliationMigrationError(
            "Bank Reconciliation review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BANK_RECONCILIATIONS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "target_reconciliations_created": False,
        "clearing_state_changed": False,
        "statement_lines_created": False,
        "gl_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "BANK_RECONCILIATIONS_DRY_RUN_READY"
        db.flush()

    return BankReconciliationDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        reviewable=reviewable,
        skipped_review=skipped,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


def commit_bank_reconciliations(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> BankReconciliationCommitResult:
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if fingerprint != expected_fingerprint:
        raise BuildiumBankReconciliationMigrationError(
            "Buildium Bank Reconciliation dry run is stale; review again before commit."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumBankReconciliationMigrationError(
            "Commit requires the exact latest Buildium Bank Reconciliation dry run."
        )

    preview = dry_run_bank_reconciliations(
        db, run=run, records=records, resolutions=resolutions
    )
    if preview.invalid:
        raise BuildiumBankReconciliationMigrationError(
            "Buildium Bank Reconciliation commit is blocked while invalid records remain."
        )

    review = _normalize_resolutions(resolutions)
    unresolved = [
        row["source_id"]
        for row in preview.rows
        if row["resolution_action"] is None
    ]
    if unresolved:
        raise BuildiumBankReconciliationMigrationError(
            "Bank Reconciliation migration requires explicit review for source IDs: "
            + ", ".join(unresolved)
        )

    rows: list[dict[str, Any]] = []
    matched = skipped = 0
    changed = False
    review_recorded = False

    for row in preview.rows:
        source_id = row["source_id"]
        prior = _mapping(
            db,
            run=run,
            resource="BANK_RECONCILIATIONS",
            source_id=source_id,
            target_entity="BANK_RECONCILIATION",
        )
        if prior is not None:
            rows.append({
                "source_id": source_id,
                "target_reconciliation_id": prior.target_id,
                "replayed": True,
            })
            continue

        resolution = review[source_id]
        if resolution["action"] == "SKIP":
            skipped += 1
            continue

        target_id = resolution["target_reconciliation_id"]
        source, reason = _source_record(
            next(
                record
                for record in records
                if _positive_id(record.get("Id")) == source_id
            )
        )
        if source is None:
            raise BuildiumBankReconciliationMigrationError(reason or "Invalid source record.")
        bank_mapping = _bank_dependency(
            db, run=run, source_id=source["bank_source_id"]
        )
        target = _target_reconciliation(db, run=run, target_id=target_id)
        if (
            bank_mapping is None
            or target is None
            or not _matches_source(target, source, bank_mapping.target_id)
        ):
            raise BuildiumBankReconciliationMigrationError(
                "Reviewed target reconciliation changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BANK_RECONCILIATIONS",
                source_id=source_id,
                target_entity="BANK_RECONCILIATION",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_id": source_id,
            "target_reconciliation_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True

    if changed:
        run.status = "BANK_RECONCILIATIONS_RECONCILED"
        db.flush()
    elif skipped and not rows:
        run.status = "BANK_RECONCILIATIONS_REVIEWED"
        db.flush()
        review_recorded = True

    return BankReconciliationCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        matched_existing=matched,
        skipped_review=skipped,
        warning_count=preview.warning_count,
        rows=rows,
    )
