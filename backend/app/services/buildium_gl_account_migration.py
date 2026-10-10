"""Buildium General Ledger account identity mapping for Phase 4.14.

This batch maps Buildium GL account identities only to already-existing target
GLAccount rows. It never creates or updates a chart-of-accounts row and never
creates balances, journal entries, bank records, or historical accounting.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun


class BuildiumGLAccountMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class GLAccountDryRunResult:
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
class GLAccountCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_inactive: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


_TYPE_MAP = {
    "Asset": "ASSET",
    "Liability": "LIABILITY",
    "Equity": "EQUITY",
    "Income": "INCOME",
    "Expense": "EXPENSE",
}


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


def _required_text(
    value: Any,
    *,
    field: str,
    max_length: int,
) -> tuple[str | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, f"{field} is required."
    if len(text) > max_length:
        return None, f"{field} exceeds {max_length} characters."
    return text, None


def _active(value: Any) -> tuple[bool | None, str | None]:
    if isinstance(value, bool):
        return value, None
    return None, "IsActive must be a boolean from the Buildium GL account resource."


def _account_type(value: Any) -> tuple[str | None, str | None]:
    text = _clean(value)
    if text not in _TYPE_MAP:
        return None, (
            "Type must be one of Asset, Liability, Equity, Income, or Expense."
        )
    return _TYPE_MAP[text], None


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumGLAccountMigrationError(
                "GL account review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumGLAccountMigrationError(
                f"Duplicate GL account review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumGLAccountMigrationError(
                "GL account review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_gl_account_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                raise BuildiumGLAccountMigrationError(
                    "MATCH_EXISTING requires a positive target GL account ID."
                )
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                raise BuildiumGLAccountMigrationError(
                    "MATCH_EXISTING requires a positive target GL account ID."
                )
            if target_id < 1:
                raise BuildiumGLAccountMigrationError(
                    "MATCH_EXISTING requires a positive target GL account ID."
                )
        elif target_id is not None:
            raise BuildiumGLAccountMigrationError(
                "target_gl_account_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_gl_account_id": target_id,
        }
    return result


def _parent_mapping(
    db: Session,
    *,
    run: PlatformMigrationRun,
    parent_source_id: str | None,
) -> PlatformMigrationItem | None:
    if parent_source_id is None:
        return None
    row = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == "GL_ACCOUNTS",
            PlatformMigrationItem.source_id == parent_source_id,
        )
        .first()
    )
    if row is not None and row.target_entity != "GL_ACCOUNT":
        raise BuildiumGLAccountMigrationError(
            f"Buildium parent GL account mapping for source ID {parent_source_id} is inconsistent."
        )
    return row


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for record in records:
        source_id = _positive_id(record.get("Id"))
        parent_source_id = _positive_id(record.get("ParentGLAccountId"))
        parent = _parent_mapping(
            db,
            run=run,
            parent_source_id=parent_source_id,
        )
        snapshot.append(
            {
                "source_id": source_id,
                "parent_source_id": parent_source_id,
                "parent_mapping": (
                    {
                        "target_id": parent.target_id,
                        "source_fingerprint": parent.source_fingerprint,
                    }
                    if parent is not None
                    else None
                ),
            }
        )
    return snapshot


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
        "resource": "GL_ACCOUNTS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "include_inactive": include_inactive,
        "records": records,
        "resolutions": [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ],
        "parent_mapping_dependencies": _dependency_snapshot(
            db,
            run=run,
            records=records,
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


def _target(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> GLAccount | None:
    return (
        db.query(GLAccount)
        .filter(
            GLAccount.id == target_id,
            GLAccount.organization_id == run.organization_id,
            GLAccount.deleted_at.is_(None),
        )
        .first()
    )


def dry_run_gl_accounts(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> GLAccountDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumGLAccountMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumGLAccountMigrationError(
            "At least one Buildium GL account record is required."
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
                    "reason": "Buildium GL account Id must be a positive integer.",
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
                    "reason": "Duplicate Buildium GL account Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        seen.add(source_id)

        number, number_error = _required_text(
            record.get("AccountNumber"),
            field="AccountNumber",
            max_length=20,
        )
        name, name_error = _required_text(
            record.get("Name"),
            field="Name",
            max_length=255,
        )
        account_type, type_error = _account_type(record.get("Type"))
        is_active, active_error = _active(record.get("IsActive"))
        parent_raw = record.get("ParentGLAccountId")
        parent_source_id = None
        parent_error = None
        if parent_raw not in (None, "", 0, "0"):
            parent_source_id = _positive_id(parent_raw)
            if parent_source_id is None:
                parent_error = (
                    "ParentGLAccountId must be a positive integer when supplied."
                )
            elif parent_source_id == source_id:
                parent_error = "A Buildium GL account cannot be its own parent."

        errors = [
            item
            for item in (
                number_error,
                name_error,
                type_error,
                active_error,
                parent_error,
            )
            if item is not None
        ]
        if errors:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": " ".join(errors),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        if is_active is False and not include_inactive:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Inactive Buildium GL account excluded by dry-run settings.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            skipped_inactive += 1
            continue

        parent_mapping = _parent_mapping(
            db,
            run=run,
            parent_source_id=parent_source_id,
        )
        if parent_source_id is not None and parent_mapping is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": (
                        f"Buildium parent GL account {parent_source_id} must already "
                        "have a durable GL_ACCOUNT mapping in this migration run."
                    ),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        target_parent_id = parent_mapping.target_id if parent_mapping else None
        valid_ids.add(source_id)
        warnings = [
            "This batch maps GL account identity only; it creates no target account, balance, journal entry, bank account, or historical accounting transaction.",
            "Buildium subtype, default-account flags, contra-account flags, bank-account flags, cash-flow classification, excluded-cash flags and credit-card flags remain source evidence only and are not promoted into target configuration.",
        ]
        candidates = (
            db.query(GLAccount)
            .filter(
                GLAccount.organization_id == run.organization_id,
                GLAccount.gl_number == number,
                GLAccount.deleted_at.is_(None),
            )
            .order_by(GLAccount.id.asc())
            .limit(5)
            .all()
        )
        if len(candidates) == 1:
            warnings.append(
                f"Possible existing target GL account match by exact account number: local GL account #{candidates[0].id}; explicit MATCH_EXISTING review is required."
            )
        elif len(candidates) > 1:
            warnings.append(
                "Multiple target GL accounts share the exact source account number; explicit review is required and no candidate is auto-selected."
            )
        else:
            warnings.append(
                "No existing target GL account with this exact account number was found; this batch does not create chart-of-accounts rows."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_gl_account_id"] if resolution else None

        if durable is not None:
            if durable.target_entity != "GL_ACCOUNT":
                raise BuildiumGLAccountMigrationError(
                    "Buildium GL account mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumGLAccountMigrationError(
                    f"Buildium source GL account ID {source_id} already has a durable "
                    "mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source GL account ID {source_id} is already durably mapped "
                f"to local GL account #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target(db, run=run, target_id=target_id)
            if target is None:
                raise BuildiumGLAccountMigrationError(
                    f"Reviewed target GL account #{target_id} is not in the target organization."
                )
            if target.gl_number != number:
                raise BuildiumGLAccountMigrationError(
                    "Reviewed target GL account number no longer matches the exact Buildium source account number."
                )
            if target.account_type != account_type:
                raise BuildiumGLAccountMigrationError(
                    "Reviewed target GL account type does not match the Buildium source account type."
                )
            if target.sub_account_of != target_parent_id:
                raise BuildiumGLAccountMigrationError(
                    "Reviewed target GL parent relationship does not match the current durable Buildium parent mapping."
                )
            if target.name != name:
                warnings.append(
                    f"Buildium source GL name {name!r} differs from target name {target.name!r}; identity mapping does not overwrite the target."
                )
            if bool(target.is_active) != bool(is_active):
                warnings.append(
                    "Buildium and target active states differ; identity mapping does not activate or deactivate the target account."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local GL account #{target.id}; commit creates durable mapping metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium GL account review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_gl_account_id": None,
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
                    "account_number": number,
                    "name": name,
                    "account_type": account_type,
                    "sub_type": _clean(record.get("SubType")),
                    "is_active": is_active,
                    "parent_source_id": parent_source_id,
                    "target_parent_gl_account_id": target_parent_id,
                    "is_default_gl_account": record.get("IsDefaultGLAccount"),
                    "is_contra_account": record.get("IsContraAccount"),
                    "is_bank_account": record.get("IsBankAccount"),
                    "cash_flow_classification": _clean(
                        record.get("CashFlowClassification")
                    ),
                    "exclude_from_cash_balances": record.get(
                        "ExcludeFromCashBalances"
                    ),
                    "is_credit_card_account": record.get("IsCreditCardAccount"),
                    "target_gl_account_id": target_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_gl_account_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - valid_ids, key=int)
    if unknown:
        raise BuildiumGLAccountMigrationError(
            "GL account review decisions may reference only otherwise-valid "
            "source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "GL_ACCOUNTS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_inactive": skipped_inactive,
        "skipped_review": skipped_review,
        "invalid": invalid,
        "warning_count": warning_count,
        "gl_accounts_created": False,
        "gl_accounts_updated": False,
        "balances_created": False,
        "transactions_created": False,
        "bank_accounts_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return GLAccountDryRunResult(
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


def commit_gl_accounts(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> GLAccountCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumGLAccountMigrationError(
            "Commit payload, parent mapping state or GL account review state does "
            "not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumGLAccountMigrationError(
            "Commit requires the exact latest successful Buildium GL account dry run."
        )

    preview = dry_run_gl_accounts(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumGLAccountMigrationError(
            "GL account mapping commit is blocked while the dry run contains invalid records."
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
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            missing.append(source_id)
    if missing:
        raise BuildiumGLAccountMigrationError(
            "GL account controlled mapping requires explicit MATCH_EXISTING or "
            "SKIP review for every valid source row: "
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
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "GL_ACCOUNT":
                raise BuildiumGLAccountMigrationError(
                    "Buildium GL account mapping is inconsistent."
                )
            target = _target(db, run=run, target_id=prior.target_id)
            if target is None:
                raise BuildiumGLAccountMigrationError(
                    "Previously mapped target GL account is missing or out of organization scope."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_gl_account_id": target.id,
                    "replayed": True,
                }
            )
            continue

        target_id = resolution_map[source_id]["target_gl_account_id"]
        target = _target(db, run=run, target_id=target_id)
        if target is None:
            raise BuildiumGLAccountMigrationError(
                f"Reviewed target GL account #{target_id} is no longer in scope."
            )
        mapped = row["mapped"]
        if target.gl_number != mapped["account_number"]:
            raise BuildiumGLAccountMigrationError(
                "Reviewed target GL account number changed after dry run."
            )
        if target.account_type != mapped["account_type"]:
            raise BuildiumGLAccountMigrationError(
                "Reviewed target GL account type changed after dry run."
            )
        if target.sub_account_of != mapped["target_parent_gl_account_id"]:
            raise BuildiumGLAccountMigrationError(
                "Reviewed target GL parent relationship changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="GL_ACCOUNTS",
                source_id=source_id,
                target_entity="GL_ACCOUNT",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_gl_account_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "GL_ACCOUNTS_MAPPED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "GL_ACCOUNTS_REVIEWED"
        db.flush()
        review_recorded = True

    return GLAccountCommitResult(
        fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_inactive,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
