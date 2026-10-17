"""Buildium full bank-deposit existing-target reconciliation.

This Phase 4.14 adapter consumes the documented Buildium bank Deposit response
plus the source Bank Account ID from the provider request path. The bounded
subset accepts only deposits composed entirely of already-mapped payment
transactions and reconciles them to an already-existing target Deposit.
No Deposit, DepositLine, Receipt, GL transaction, GL entry, balance,
reconciliation, or clearing state is created or changed.
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
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.receipt import Receipt


class BuildiumDepositMigrationError(ValueError):
    pass


CENT = Decimal("0.01")
MAX_ABS_MONEY = Decimal("999999999999.99")


@dataclass(frozen=True)
class DepositDryRunResult:
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
class DepositCommitResult:
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
        raise BuildiumDepositMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _normalize_payment_ids(value: Any) -> tuple[list[str] | None, str | None]:
    if not isinstance(value, list) or not value:
        return None, "PaymentTransactionIds must contain at least one Buildium payment transaction ID."
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        source_id = _positive_id(raw)
        if source_id is None:
            return None, "PaymentTransactionIds must contain only positive integer IDs."
        if source_id in seen:
            return None, "PaymentTransactionIds must not contain duplicate IDs."
        seen.add(source_id)
        result.append(source_id)
    return result, None


def _source_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    source_bank_id = _positive_id(record.get("SourceBankAccountId"))
    entry_date, date_error = _date_value(record.get("EntryDate"))
    amount, amount_error = _money(record.get("TotalAmount"))
    payment_ids, payment_error = _normalize_payment_ids(record.get("PaymentTransactionIds"))
    lines = record.get("Lines")
    lines_error = None
    if lines not in (None, []):
        lines_error = (
            "This bounded Buildium Deposit batch supports only payment-only deposits; "
            "standalone Lines remain blocked because target Deposit grouping cannot "
            "preserve their accounting semantics."
        )

    errors = [
        item
        for item in (
            None if source_id is not None else "Buildium Deposit Id must be a positive integer.",
            None if source_bank_id is not None else "SourceBankAccountId retrieval context must be a positive integer.",
            date_error,
            amount_error,
            payment_error,
            lines_error,
        )
        if item
    ]
    if errors:
        return None, " ".join(errors)

    return {
        "source_id": source_id,
        "source_bank_source_id": source_bank_id,
        "entry_date": entry_date,
        "amount": amount,
        "payment_source_ids": payment_ids,
    }, None


def _normalize_resolutions(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumDepositMigrationError(
                "Deposit review requires unique positive source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumDepositMigrationError(
                "Deposit review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_deposit_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumDepositMigrationError(
                    "MATCH_EXISTING requires a positive target_deposit_id."
                )
        elif target_id is not None:
            raise BuildiumDepositMigrationError(
                "target_deposit_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_deposit_id": target_id,
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


def _receipt_posted_to_cash_gl(
    db: Session,
    *,
    run: PlatformMigrationRun,
    receipt: Receipt,
    cash_gl_account_id: int,
) -> bool:
    if (
        receipt.organization_id != run.organization_id
        or not receipt.is_active
        or receipt.deleted_at is not None
        or receipt.is_reversed
        or receipt.reversal_of_id is not None
        or receipt.cash_gl_account_id != cash_gl_account_id
        or receipt.gl_transaction_id is None
    ):
        return False
    txn = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.id == receipt.gl_transaction_id,
            GLTransaction.organization_id == run.organization_id,
            GLTransaction.transaction_type == "RECEIPT",
            GLTransaction.source_type == "receipt",
            GLTransaction.source_id == receipt.id,
            GLTransaction.transaction_date == receipt.receipt_date,
            GLTransaction.is_reversed.is_(False),
            GLTransaction.reversal_of_id.is_(None),
        )
        .first()
    )
    if txn is None:
        return False
    matching_cash = (
        db.query(GLEntry)
        .filter(
            GLEntry.transaction_id == txn.id,
            GLEntry.organization_id == run.organization_id,
            GLEntry.gl_account_id == cash_gl_account_id,
            GLEntry.debit == receipt.amount,
            GLEntry.credit == Decimal("0.00"),
        )
        .count()
    )
    return matching_cash == 1


def _resolved_dependencies(
    db: Session,
    *,
    run: PlatformMigrationRun,
    source: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    bank_mapping = _mapping(
        db,
        run=run,
        resource="BANK_ACCOUNTS",
        source_id=source["source_bank_source_id"],
        target_entity="BANK_ACCOUNT",
    )
    if bank_mapping is None:
        return None, "Deposit migration requires a durable same-run Buildium Bank Account mapping."
    bank = _target_bank(db, run=run, target_id=bank_mapping.target_id)
    if bank is None:
        return None, "Mapped Bank Account is no longer active in the target organization."

    receipts: list[Receipt] = []
    payment_mappings: list[PlatformMigrationItem] = []
    for payment_source_id in source["payment_source_ids"]:
        mapping = _mapping(
            db,
            run=run,
            resource="LEASE_PAYMENTS",
            source_id=payment_source_id,
            target_entity="RECEIPT_RELATIONSHIP",
        )
        if mapping is None:
            return None, (
                f"Buildium payment transaction {payment_source_id} must already have "
                "a same-run LEASE_PAYMENTS -> RECEIPT_RELATIONSHIP mapping."
            )
        receipt = (
            db.query(Receipt)
            .filter(
                Receipt.id == mapping.target_id,
                Receipt.organization_id == run.organization_id,
            )
            .first()
        )
        if receipt is None or not _receipt_posted_to_cash_gl(
            db, run=run, receipt=receipt, cash_gl_account_id=bank.gl_account_id
        ):
            return None, (
                f"Mapped Receipt for Buildium payment transaction {payment_source_id} "
                "is no longer active, unreversed, same-organization, or posted to "
                "the mapped Bank Account cash GL."
            )
        receipts.append(receipt)
        payment_mappings.append(mapping)

    if len({receipt.id for receipt in receipts}) != len(receipts):
        return None, "Different Buildium payment transaction IDs cannot resolve to the same target Receipt."

    receipt_total = sum((Decimal(receipt.amount).quantize(CENT) for receipt in receipts), Decimal("0.00"))
    if receipt_total != source["amount"]:
        return None, (
            "Buildium Deposit TotalAmount must exactly equal the sum of all mapped "
            "target Receipt amounts for this payment-only subset."
        )

    return {
        "bank": bank,
        "bank_mapping": bank_mapping,
        "receipts": receipts,
        "payment_mappings": payment_mappings,
    }, None


def _target_snapshot(target: Deposit | None) -> dict[str, Any] | None:
    if target is None:
        return None
    return {
        "id": target.id,
        "organization_id": target.organization_id,
        "bank_gl_account_id": target.bank_gl_account_id,
        "deposit_date": target.deposit_date.isoformat(),
        "total": f"{Decimal(target.total).quantize(CENT):.2f}",
        "is_active": bool(target.is_active),
        "deleted_at": target.deleted_at.isoformat() if target.deleted_at else None,
        "receipt_ids": sorted(line.receipt_id for line in target.lines),
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
                    "target_gl_account_id": deps["bank"].gl_account_id,
                },
                "payments": [
                    {
                        "source_id": mapping.source_id,
                        "target_id": mapping.target_id,
                        "source_fingerprint": mapping.source_fingerprint,
                        "receipt_snapshot": {
                            "id": receipt.id,
                            "amount": f"{Decimal(receipt.amount).quantize(CENT):.2f}",
                            "receipt_date": receipt.receipt_date.isoformat(),
                            "cash_gl_account_id": receipt.cash_gl_account_id,
                            "gl_transaction_id": receipt.gl_transaction_id,
                            "is_active": bool(receipt.is_active),
                            "is_reversed": bool(receipt.is_reversed),
                            "deleted_at": receipt.deleted_at.isoformat() if receipt.deleted_at else None,
                        },
                    }
                    for mapping, receipt in zip(deps["payment_mappings"], deps["receipts"])
                ],
            }
        resolution = review.get(source["source_id"])
        reviewed_target = None
        if resolution and resolution["action"] == "MATCH_EXISTING":
            reviewed_target = _target_snapshot(
                db.query(Deposit)
                .filter(
                    Deposit.id == resolution["target_deposit_id"],
                    Deposit.organization_id == run.organization_id,
                )
                .first()
            )
        result.append(
            {
                "source_id": source["source_id"],
                "dependencies": dependency_data,
                "reviewed_target": reviewed_target,
            }
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
        "resource": "BANK_DEPOSITS",
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
    db: Session,
    *,
    run: PlatformMigrationRun,
    target: Deposit,
    source: dict[str, Any],
    deps: dict[str, Any],
) -> bool:
    if (
        target.organization_id != run.organization_id
        or not target.is_active
        or target.deleted_at is not None
        or target.bank_gl_account_id != deps["bank"].gl_account_id
        or target.deposit_date != source["entry_date"]
        or Decimal(target.total).quantize(CENT) != source["amount"]
    ):
        return False
    expected_receipt_ids = sorted(receipt.id for receipt in deps["receipts"])
    actual_lines = (
        db.query(DepositLine)
        .filter(
            DepositLine.deposit_id == target.id,
            DepositLine.organization_id == run.organization_id,
        )
        .all()
    )
    actual_receipt_ids = sorted(line.receipt_id for line in actual_lines)
    return actual_receipt_ids == expected_receipt_ids and len(actual_lines) == len(expected_receipt_ids)


def dry_run_deposits(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> DepositDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumDepositMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumDepositMigrationError(
            "At least one Buildium Deposit record is required."
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
                "reason": "Duplicate Buildium Deposit Id in this dry run.",
                "mapped": None,
                "warnings": [],
                "resolution_action": None,
                "resolution_target_deposit_id": None,
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
                "resolution_target_deposit_id": None,
            })
            invalid += 1
            continue

        deps, dependency_error = _resolved_dependencies(db, run=run, source=source)
        if deps is None:
            rows.append({
                "source_id": source["source_id"],
                "reviewable": False,
                "reason": dependency_error,
                "mapped": None,
                "warnings": [],
                "resolution_action": None,
                "resolution_target_deposit_id": None,
            })
            invalid += 1
            continue

        valid_ids.add(source["source_id"])
        resolution = review.get(source["source_id"])
        prior = _mapping(
            db,
            run=run,
            resource="BANK_DEPOSITS",
            source_id=source["source_id"],
            target_entity="DEPOSIT_RELATIONSHIP",
        )
        warnings = [
            "This bounded batch reconciles only payment-only Buildium bank Deposits whose PaymentTransactionIds are already mapped to target Receipts.",
            "Standalone Buildium Deposit Lines remain blocked; no debit/credit direction or extra accounting history is inferred.",
            "A matched target Deposit proves only internal receipt grouping, not external bank settlement, clearing, or reconciliation.",
            "No Deposit, DepositLine, Receipt, GL transaction, GL entry, balance, or clearing state is created or changed.",
        ]
        action = resolution["action"] if resolution else None
        target_id = resolution["target_deposit_id"] if resolution else None

        if prior is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != prior.target_id
            ):
                raise BuildiumDepositMigrationError(
                    f"Buildium Deposit source ID {source['source_id']} is already mapped and cannot be re-resolved."
                )
            target = (
                db.query(Deposit)
                .filter(
                    Deposit.id == prior.target_id,
                    Deposit.organization_id == run.organization_id,
                )
                .first()
            )
            if target is None or not _matches_target(
                db, run=run, target=target, source=source, deps=deps
            ):
                rows.append({
                    "source_id": source["source_id"],
                    "reviewable": False,
                    "reason": "Previously mapped target Deposit no longer matches the reviewed source/dependency contract.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": None,
                    "resolution_target_deposit_id": None,
                })
                invalid += 1
                warning_count += len(warnings)
                continue
            action = "ALREADY_MAPPED"
            target_id = prior.target_id
            warnings.append(
                f"Buildium Deposit is already durably mapped to local Deposit #{prior.target_id}; commit will replay."
            )

        if action == "SKIP":
            rows.append({
                "source_id": source["source_id"],
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Deposit review.",
                "mapped": None,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_deposit_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue

        if action == "MATCH_EXISTING":
            target = (
                db.query(Deposit)
                .filter(
                    Deposit.id == target_id,
                    Deposit.organization_id == run.organization_id,
                )
                .first()
            )
            if target is None:
                raise BuildiumDepositMigrationError(
                    f"Reviewed target Deposit #{target_id} is not in the target organization."
                )
            if not _matches_target(db, run=run, target=target, source=source, deps=deps):
                raise BuildiumDepositMigrationError(
                    "Reviewed target Deposit no longer matches the Buildium bank, date, total, or exact mapped Receipt membership contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Deposit #{target.id}; commit creates migration metadata only."
            )
        elif action is None:
            candidates = (
                db.query(Deposit)
                .filter(
                    Deposit.organization_id == run.organization_id,
                    Deposit.bank_gl_account_id == deps["bank"].gl_account_id,
                    Deposit.deposit_date == source["entry_date"],
                    Deposit.total == source["amount"],
                    Deposit.is_active.is_(True),
                    Deposit.deleted_at.is_(None),
                )
                .order_by(Deposit.id.asc())
                .limit(10)
                .all()
            )
            exact = [
                candidate
                for candidate in candidates
                if _matches_target(db, run=run, target=candidate, source=source, deps=deps)
            ]
            if len(exact) == 1:
                warnings.append(
                    f"Possible exact existing target Deposit match: Deposit #{exact[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(exact) > 1:
                warnings.append(
                    "Multiple exact target Deposits match; no candidate is auto-selected."
                )
            else:
                warnings.append(
                    "No exact target Deposit exists; this bounded batch does not create one."
                )

        rows.append({
            "source_id": source["source_id"],
            "reviewable": True,
            "reason": None,
            "mapped": {
                "source_bank_account_id": int(source["source_bank_source_id"]),
                "target_bank_account_id": deps["bank"].id,
                "target_bank_gl_account_id": deps["bank"].gl_account_id,
                "entry_date": source["entry_date"].isoformat(),
                "total_amount": f"{source['amount']:.2f}",
                "payment_transaction_ids": [int(value) for value in source["payment_source_ids"]],
                "target_receipt_ids": [receipt.id for receipt in deps["receipts"]],
                "standalone_lines_supported": False,
                "target_deposit_created": False,
                "external_settlement_verified": False,
            },
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_deposit_id": target_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    extra = sorted(set(review) - valid_ids, key=int)
    if extra:
        raise BuildiumDepositMigrationError(
            "Deposit review contains source IDs that are not valid in this dry run: "
            + ", ".join(extra)
        )

    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = {
            "resource": "BANK_DEPOSITS",
            "total": len(records),
            "reviewable": reviewable,
            "skipped_review": skipped,
            "invalid": invalid,
            "warning_count": warning_count,
            "target_deposit_created": False,
            "receipt_history_created": False,
            "gl_history_created": False,
            "external_settlement_verified": False,
        }
        run.status = "BANK_DEPOSITS_DRY_RUN_READY"
        db.flush()

    return DepositDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        reviewable=reviewable,
        skipped_review=skipped,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=run.last_dry_run_summary or {},
    )


def commit_deposits(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> DepositCommitResult:
    current = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if current != expected_fingerprint or run.last_dry_run_fingerprint != expected_fingerprint:
        raise BuildiumDepositMigrationError(
            "Buildium Deposit dry run is stale; run the exact review again before commit."
        )

    preview = dry_run_deposits(
        db, run=run, records=records, resolutions=resolutions
    )
    if preview.invalid:
        raise BuildiumDepositMigrationError(
            "Buildium Deposit commit is blocked while invalid records remain."
        )
    missing = [
        row["source_id"]
        for row in preview.rows
        if row.get("resolution_action") is None
    ]
    if missing:
        raise BuildiumDepositMigrationError(
            "Deposit migration requires explicit review for source IDs: "
            + ", ".join(missing)
        )

    review = _normalize_resolutions(resolutions)
    rows: list[dict[str, Any]] = []
    matched = skipped = 0
    changed = review_recorded = False

    for row in preview.rows:
        source_id = row["source_id"]
        action = row.get("resolution_action")
        if action == "SKIP":
            skipped += 1
            review_recorded = True
            continue
        if action == "ALREADY_MAPPED":
            rows.append({
                "source_id": source_id,
                "target_deposit_id": row["resolution_target_deposit_id"],
                "replayed": True,
            })
            continue

        target_id = int(review[source_id]["target_deposit_id"])
        source_record = next(
            record for record in records if _positive_id(record.get("Id")) == source_id
        )
        source, _ = _source_record(source_record)
        deps, dependency_error = _resolved_dependencies(db, run=run, source=source)
        if deps is None:
            raise BuildiumDepositMigrationError(
                dependency_error or "Buildium Deposit dependencies changed after dry run."
            )
        target = (
            db.query(Deposit)
            .filter(
                Deposit.id == target_id,
                Deposit.organization_id == run.organization_id,
            )
            .first()
        )
        if target is None or not _matches_target(
            db, run=run, target=target, source=source, deps=deps
        ):
            raise BuildiumDepositMigrationError(
                "Reviewed target Deposit changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BANK_DEPOSITS",
                source_id=source_id,
                target_entity="DEPOSIT_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_id": source_id,
            "target_deposit_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True

    if changed:
        run.status = "BANK_DEPOSITS_RECONCILED"
        db.flush()
    elif review_recorded and not rows:
        run.status = "BANK_DEPOSITS_REVIEWED"
        db.flush()

    return DepositCommitResult(
        fingerprint=preview.fingerprint,
        replayed=not changed and not review_recorded,
        matched_existing=matched,
        skipped_review=skipped,
        warning_count=preview.warning_count,
        rows=rows,
    )
