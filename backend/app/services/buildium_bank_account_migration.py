"""Buildium Bank Account identity mapping for Phase 4.14.

This batch maps a Buildium Bank Account only to an already-existing target
BankAccount through the already-verified Buildium GL Account mapping. Provider
account/routing numbers, unmasked numbers, balance, electronic-payment limits
and check-printing configuration are never copied, exposed, or audited.

Buildium Checking/Savings is not equivalent to the target OPERATING/ESCROW
classification and is retained only as source evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun


class BuildiumBankAccountMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class BankAccountDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_inactive: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class BankAccountCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_inactive: int
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
        raise BuildiumBankAccountMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _source_gl_id(record: dict[str, Any]) -> str | None:
    gl = record.get("GLAccount")
    return _positive_id(gl.get("Id")) if isinstance(gl, dict) else None


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        source_id = _positive_id(record.get("Id"))
        gl_source_id = _source_gl_id(record)
        mapping = (
            _mapping(
                db,
                run=run,
                resource="GL_ACCOUNTS",
                source_id=gl_source_id,
                target_entity="GL_ACCOUNT",
            )
            if gl_source_id is not None
            else None
        )
        result.append(
            {
                "bank_account_source_id": source_id,
                "gl_account_source_id": gl_source_id,
                "gl_account": (
                    {
                        "target_id": mapping.target_id,
                        "source_fingerprint": mapping.source_fingerprint,
                    }
                    if mapping is not None
                    else None
                ),
            }
        )
    return result


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumBankAccountMigrationError(
                "Bank Account review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumBankAccountMigrationError(
                f"Duplicate Bank Account review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBankAccountMigrationError(
                "Bank Account review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_bank_account_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumBankAccountMigrationError(
                    "MATCH_EXISTING requires a positive target Bank Account ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumBankAccountMigrationError(
                    "MATCH_EXISTING requires a positive target Bank Account ID."
                )
            if target < 1:
                raise BuildiumBankAccountMigrationError(
                    "MATCH_EXISTING requires a positive target Bank Account ID."
                )
        elif target is not None:
            raise BuildiumBankAccountMigrationError(
                "target_bank_account_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_bank_account_id": target,
        }
    return result


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "BANK_ACCOUNTS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "include_inactive": include_inactive,
        "records": records,
        "resolutions": [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ],
        "dependency_mappings": _dependency_snapshot(db, run=run, records=records),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _target_bank_account(
    db: Session,
    *,
    run: PlatformMigrationRun,
    bank_account_id: int,
) -> BankAccount | None:
    return (
        db.query(BankAccount)
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.organization_id == run.organization_id,
            BankAccount.is_active.is_(True),
            BankAccount.deleted_at.is_(None),
        )
        .first()
    )


def dry_run_bank_accounts(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> BankAccountDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumBankAccountMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumBankAccountMigrationError(
            "At least one Buildium Bank Account record is required."
        )

    fingerprint = _fingerprint(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids: set[str] = set()
    reviewable = skipped_inactive = skipped_review = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is None:
            rows.append(
                {
                    "source_id": None,
                    "reviewable": False,
                    "reason": "Buildium Bank Account Id must be a positive integer.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if source_id in seen:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Duplicate Buildium Bank Account Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        seen.add(source_id)

        name = _clean(record.get("Name"))
        if name is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Buildium Bank Account Name is required.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if len(name) > 255:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Buildium Bank Account Name exceeds the bounded 255-character migration limit.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        is_active = record.get("IsActive")
        if not isinstance(is_active, bool):
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Buildium Bank Account IsActive must be boolean.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if not is_active and not include_inactive:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Inactive Buildium Bank Account excluded by this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            skipped_inactive += 1
            continue

        source_type = _clean(record.get("BankAccountType"))
        if source_type not in {"Checking", "Savings"}:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Buildium BankAccountType must be Checking or Savings.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        gl_source_id = _source_gl_id(record)
        if gl_source_id is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Buildium Bank Account requires a positive GLAccount Id.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        gl_mapping = _mapping(
            db,
            run=run,
            resource="GL_ACCOUNTS",
            source_id=gl_source_id,
            target_entity="GL_ACCOUNT",
        )
        if gl_mapping is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": f"Bank Account mapping requires durable Buildium GL Account mapping {gl_source_id}.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        gl_row = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
            )
            .first()
        )
        if gl_row is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Mapped Buildium GL Account is no longer in organization scope.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if gl_row.account_type != "ASSET":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Mapped target GL Account must remain an ASSET account for Bank Account reconciliation.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        valid_ids.add(source_id)
        warnings = [
            "This batch maps Buildium Bank Account identity only; it never creates or updates a target BankAccount.",
            "Buildium Checking/Savings is not equivalent to target OPERATING/ESCROW and is never promoted into the target classification.",
            "Provider account number, unmasked account number, routing number, balance, country, description, electronic-payment settings and check-printing settings are source evidence only and are not returned, persisted, compared, or audited.",
        ]

        candidates = (
            db.query(BankAccount)
            .filter(
                BankAccount.organization_id == run.organization_id,
                BankAccount.gl_account_id == gl_row.id,
                BankAccount.is_active.is_(True),
                BankAccount.deleted_at.is_(None),
            )
            .order_by(BankAccount.id.asc())
            .limit(5)
            .all()
        )
        if len(candidates) == 1:
            warnings.append(
                f"Possible existing Bank Account mapped to the reviewed GL account: local Bank Account #{candidates[0].id}; explicit MATCH_EXISTING review is required."
            )
            if candidates[0].name != name:
                warnings.append(
                    "Buildium Bank Account name differs from the local display name; mapping does not overwrite either name."
                )
        elif len(candidates) > 1:
            warnings.append(
                "Multiple target Bank Accounts reference the mapped GL account; explicit review is required and no candidate is auto-selected."
            )
        else:
            warnings.append(
                "No existing target Bank Account references the mapped GL account; this batch does not create a BankAccount."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BANK_ACCOUNTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_bank_account_id"] if resolution else None

        if durable is not None:
            if durable.target_entity != "BANK_ACCOUNT":
                raise BuildiumBankAccountMigrationError(
                    "Buildium Bank Account mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumBankAccountMigrationError(
                    f"Buildium source Bank Account ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source Bank Account ID {source_id} is already durably mapped to local Bank Account #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target_bank_account(db, run=run, bank_account_id=target_id)
            if target is None:
                raise BuildiumBankAccountMigrationError(
                    f"Reviewed target Bank Account #{target_id} is not active in the target organization."
                )
            if target.gl_account_id != gl_row.id:
                raise BuildiumBankAccountMigrationError(
                    "Reviewed target Bank Account no longer references the current durable Buildium GL Account mapping."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Bank Account #{target.id}; commit creates durable identity mapping metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Bank Account identity review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_bank_account_id": None,
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
                "mapped": {
                    "name": name,
                    "source_bank_account_type": source_type,
                    "source_is_active": is_active,
                    "gl_account_source_id": gl_source_id,
                    "target_gl_account_id": gl_row.id,
                    "target_bank_account_id": target_id,
                    "sensitive_bank_fields_exposed": False,
                    "balance_imported": False,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_bank_account_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - valid_ids, key=int)
    if unknown:
        raise BuildiumBankAccountMigrationError(
            "Bank Account review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BANK_ACCOUNTS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_inactive": skipped_inactive,
        "skipped_review": skipped_review,
        "invalid": invalid,
        "warning_count": warning_count,
        "bank_accounts_created": False,
        "bank_accounts_updated": False,
        "account_numbers_copied": False,
        "routing_numbers_copied": False,
        "balances_imported": False,
        "reconciliation_state_imported": False,
        "bank_movement_created": False,
        "gl_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return BankAccountDryRunResult(
        fingerprint,
        replayed,
        len(records),
        reviewable,
        skipped_inactive,
        skipped_review,
        invalid,
        warning_count,
        rows,
        summary,
    )


def commit_bank_accounts(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> BankAccountCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumBankAccountMigrationError(
            "Commit payload, GL mapping state or Bank Account review state does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumBankAccountMigrationError(
            "Commit requires the exact latest successful Buildium Bank Account dry run."
        )

    preview = dry_run_bank_accounts(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumBankAccountMigrationError(
            "Bank Account mapping commit is blocked while the dry run contains invalid records."
        )

    resolution_map = _normalize_resolutions(resolutions)
    valid = [row for row in preview.rows if row["reviewable"]]
    missing: list[str] = []
    for row in valid:
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BANK_ACCOUNTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            missing.append(source_id)
    if missing:
        raise BuildiumBankAccountMigrationError(
            "Bank Account identity mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row: "
            + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False
    for row in valid:
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BANK_ACCOUNTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "BANK_ACCOUNT":
                raise BuildiumBankAccountMigrationError(
                    "Buildium Bank Account mapping is inconsistent."
                )
            target = _target_bank_account(db, run=run, bank_account_id=prior.target_id)
            if target is None:
                raise BuildiumBankAccountMigrationError(
                    "Previously mapped target Bank Account is missing, inactive, deleted, or out of organization scope."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_bank_account_id": target.id,
                    "replayed": True,
                }
            )
            continue

        target_id = resolution_map[source_id]["target_bank_account_id"]
        target = _target_bank_account(db, run=run, bank_account_id=target_id)
        if target is None:
            raise BuildiumBankAccountMigrationError(
                f"Reviewed target Bank Account #{target_id} is no longer active and in scope."
            )
        mapped = row["mapped"]
        if target.gl_account_id != mapped["target_gl_account_id"]:
            raise BuildiumBankAccountMigrationError(
                "Reviewed target Bank Account GL relationship changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BANK_ACCOUNTS",
                source_id=source_id,
                target_entity="BANK_ACCOUNT",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_bank_account_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "BANK_ACCOUNTS_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "BANK_ACCOUNTS_REVIEWED"
        db.flush()
        review_recorded = True

    return BankAccountCommitResult(
        fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_inactive,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
