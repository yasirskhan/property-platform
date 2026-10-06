"""Buildium Association Owner identity reconciliation for Phase 4.14.

Maps a stable Buildium Association Owner identity only to an already-existing
same-organization OWNER user. It does not create ownership accounts, HOA
memberships, board roles, dues, delinquency state, leases, or accounting data.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.user import User, UserRole


class BuildiumAssociationOwnerMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class AssociationOwnerDryRunResult:
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
class AssociationOwnerCommitResult:
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


def _source_identity(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Association Owner Id must be a positive integer."

    first_name = _clean(record.get("FirstName"))
    last_name = _clean(record.get("LastName"))
    if not first_name or not last_name:
        return None, "Buildium Association Owner FirstName and LastName are required."
    if len(first_name) > 100 or len(last_name) > 100:
        return None, "Buildium Association Owner FirstName or LastName exceeds target limits."

    email = _clean(record.get("Email"))
    if (
        email is None
        or len(email) > 255
        or not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", email)
    ):
        return None, "Buildium Association Owner Email must contain one valid email address."

    user_lease_id = None
    if record.get("UserLeaseId") is not None:
        user_lease_id = _positive_id(record.get("UserLeaseId"))
        if user_lease_id is None:
            return None, "Buildium Association Owner UserLeaseId must be a positive integer when supplied."

    return {
        "source_id": source_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email.lower(),
        "user_lease_id": user_lease_id,
    }, None


def _normalize_resolutions(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumAssociationOwnerMigrationError(
                "Association Owner review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumAssociationOwnerMigrationError(
                f"Duplicate Association Owner review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumAssociationOwnerMigrationError(
                "Association Owner review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_owner_user_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumAssociationOwnerMigrationError(
                    "MATCH_EXISTING requires a positive target_owner_user_id."
                )
        elif target_id is not None:
            raise BuildiumAssociationOwnerMigrationError(
                "target_owner_user_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_owner_user_id": target_id,
        }
    return result


def _target(
    db: Session, *, run: PlatformMigrationRun, target_id: int, active: bool = True
) -> User | None:
    query = db.query(User).filter(
        User.id == target_id,
        User.organization_id == run.organization_id,
        User.role == UserRole.OWNER,
    )
    if active:
        query = query.filter(User.is_active.is_(True), User.deleted_at.is_(None))
    return query.first()


def _target_snapshot(
    db: Session, *, run: PlatformMigrationRun, target_id: int
) -> dict[str, Any] | None:
    row = _target(db, run=run, target_id=target_id, active=False)
    if row is None:
        return None
    return {
        "id": row.id,
        "email": row.email.lower(),
        "first_name": row.first_name,
        "last_name": row.last_name,
        "is_active": bool(row.is_active),
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
    }


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    review = _normalize_resolutions(resolutions)
    snapshots = {
        source_id: _target_snapshot(
            db, run=run, target_id=item["target_owner_user_id"]
        )
        for source_id, item in review.items()
        if item["action"] == "MATCH_EXISTING"
    }
    payload = {
        "provider": "BUILDIUM",
        "resource": "HOA_OWNERS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "target_snapshots": snapshots,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _identity_matches(target: User, identity: dict[str, Any]) -> bool:
    return (
        target.email.lower() == identity["email"]
        and (target.first_name or "").strip().casefold()
        == identity["first_name"].casefold()
        and (target.last_name or "").strip().casefold()
        == identity["last_name"].casefold()
    )


def dry_run_association_owners(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> AssociationOwnerDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumAssociationOwnerMigrationError(
            "Migration run is not a Buildium run."
        )
    if not records:
        raise BuildiumAssociationOwnerMigrationError(
            "At least one Buildium Association Owner record is required."
        )

    review = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        identity, error = _source_identity(record)
        source_id = _positive_id(record.get("Id"))
        if identity is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": error,
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_owner_user_id": None,
                }
            )
            invalid += 1
            continue

        source_id = identity["source_id"]
        if source_id in seen:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Duplicate Buildium Association Owner Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_owner_user_id": None,
                }
            )
            invalid += 1
            continue
        seen.add(source_id)
        valid_ids.add(source_id)

        warnings = [
            "Association Owner identity reconciliation creates no ownership account, HOA membership, board role, dues liability, delinquency state, lease, or accounting record.",
            "Source addresses, phone numbers, notes, board-term fields and other private provider details are not promoted or stored by this identity batch.",
        ]
        if identity["user_lease_id"] is not None:
            warnings.append(
                "Buildium UserLeaseId is retained as source context only; no owner-to-unit, ownership-account, lease, or occupancy relationship is inferred."
            )

        candidate = (
            db.query(User)
            .filter(
                User.organization_id == run.organization_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                func.lower(User.email) == identity["email"],
            )
            .first()
        )
        if candidate is not None:
            warnings.append(
                f"Possible existing target OWNER match by exact source email: local OWNER #{candidate.id}; explicit MATCH_EXISTING review is required."
            )
        else:
            warnings.append(
                "No active same-organization OWNER with this exact source email was found; this batch does not create login identities."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "HOA_OWNERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = review.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_owner_user_id"] if resolution else None

        if durable is not None:
            if durable.target_entity != "OWNER_USER":
                raise BuildiumAssociationOwnerMigrationError(
                    "Buildium Association Owner mapping is inconsistent."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumAssociationOwnerMigrationError(
                    f"Buildium source Association Owner ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            action = "MATCH_EXISTING"
            target_id = durable.target_id
            warnings.append(
                f"Buildium source Association Owner ID {source_id} is already durably mapped to local OWNER #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target(db, run=run, target_id=target_id)
            if target is None:
                raise BuildiumAssociationOwnerMigrationError(
                    f"Reviewed target OWNER #{target_id} is not active in the target organization."
                )
            if not _identity_matches(target, identity):
                raise BuildiumAssociationOwnerMigrationError(
                    "Reviewed OWNER identity no longer matches the Buildium source name/email."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local OWNER #{target.id}; commit creates migration metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Association Owner review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_owner_user_id": None,
                }
            )
            skipped += 1
            warning_count += len(warnings)
            continue

        rows.append(
            {
                "source_id": source_id,
                "reviewable": True,
                "reason": None,
                "mapped": {
                    "first_name": identity["first_name"],
                    "last_name": identity["last_name"],
                    "email": identity["email"],
                    "source_user_lease_id": identity["user_lease_id"],
                    "target_owner_user_id": target_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_owner_user_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(review) - valid_ids, key=int)
    if unknown:
        raise BuildiumAssociationOwnerMigrationError(
            "Association Owner review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "HOA_OWNERS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "owner_users_created": False,
        "ownership_accounts_created": False,
        "hoa_memberships_created": False,
        "board_roles_created": False,
        "dues_or_delinquency_imported": False,
        "lease_or_occupancy_relationships_inferred": False,
        "accounting_mutation": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return AssociationOwnerDryRunResult(
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


def commit_association_owners(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> AssociationOwnerCommitResult:
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if expected_fingerprint != fingerprint:
        raise BuildiumAssociationOwnerMigrationError(
            "Commit payload, review state, or reviewed target snapshot does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumAssociationOwnerMigrationError(
            "Commit requires the exact latest successful Buildium Association Owner dry run."
        )

    preview = dry_run_association_owners(
        db, run=run, records=records, resolutions=resolutions
    )
    if preview.invalid:
        raise BuildiumAssociationOwnerMigrationError(
            "Association Owner commit is blocked while the dry run contains invalid records."
        )

    review = _normalize_resolutions(resolutions)
    for row in preview.rows:
        if not row["reviewable"]:
            continue
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "HOA_OWNERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            raise BuildiumAssociationOwnerMigrationError(
                "Association Owner controlled mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row."
            )

    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False

    for row in preview.rows:
        if not row["reviewable"]:
            continue
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "HOA_OWNERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "OWNER_USER":
                raise BuildiumAssociationOwnerMigrationError(
                    "Buildium Association Owner mapping is inconsistent."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_owner_user_id": prior.target_id,
                    "replayed": True,
                }
            )
            continue

        target_id = review[source_id]["target_owner_user_id"]
        target = _target(db, run=run, target_id=target_id)
        if target is None:
            raise BuildiumAssociationOwnerMigrationError(
                f"Reviewed target OWNER #{target_id} is no longer active."
            )
        if not _identity_matches(target, row["mapped"]):
            raise BuildiumAssociationOwnerMigrationError(
                "Reviewed target OWNER identity changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="HOA_OWNERS",
                source_id=source_id,
                target_entity="OWNER_USER",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_owner_user_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "HOA_OWNERS_MAPPED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "HOA_OWNERS_REVIEWED"
        db.flush()
        review_recorded = True

    return AssociationOwnerCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        matched_existing=matched,
        skipped_review=preview.skipped_review,
        warning_count=preview.warning_count,
        rows=rows,
    )
