"""Buildium Association identity reconciliation for Phase 4.14.

This bounded adapter reconciles a stable Buildium Association identity to an
already-existing same-organization HOAAssociation. It does not create or edit
HOA associations, property memberships, owners, contacts, dues, reserves,
bank-account mappings, board records, notices, or accounting history.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.hoa_association import HOAAssociation
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun


class BuildiumAssociationMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class AssociationDryRunResult:
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
class AssociationCommitResult:
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


def _source_identity(
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Association Id must be a positive integer."

    name = _clean(record.get("Name"))
    if name is None:
        return None, "Buildium Association Name is required."
    if len(name) > 160:
        return None, "Buildium Association Name exceeds the target 160-character limit."

    is_active = record.get("IsActive")
    if not isinstance(is_active, bool):
        return None, "Buildium Association IsActive must be a boolean."

    return {
        "source_id": source_id,
        "name": name,
        "is_active": is_active,
    }, None


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumAssociationMigrationError(
                "Association review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumAssociationMigrationError(
                f"Duplicate Association review decision for source ID {source_id}."
            )

        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumAssociationMigrationError(
                "Association review supports only MATCH_EXISTING or SKIP."
            )

        target_id = item.get("target_hoa_association_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumAssociationMigrationError(
                    "MATCH_EXISTING requires a positive target_hoa_association_id."
                )
        elif target_id is not None:
            raise BuildiumAssociationMigrationError(
                "target_hoa_association_id is only valid for MATCH_EXISTING."
            )

        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_hoa_association_id": target_id,
        }
    return result


def _target(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> HOAAssociation | None:
    return (
        db.query(HOAAssociation)
        .filter(
            HOAAssociation.id == target_id,
            HOAAssociation.organization_id == run.organization_id,
        )
        .first()
    )


def _target_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> dict[str, Any] | None:
    row = _target(db, run=run, target_id=target_id)
    if row is None:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "name_key": row.name_key,
        "is_active": bool(row.is_active),
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
            db,
            run=run,
            target_id=item["target_hoa_association_id"],
        )
        for source_id, item in review.items()
        if item["action"] == "MATCH_EXISTING"
    }
    payload = {
        "provider": "BUILDIUM",
        "resource": "HOA_ASSOCIATIONS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "target_snapshots": snapshots,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _identity_matches(
    target: HOAAssociation,
    identity: dict[str, Any],
) -> bool:
    return (
        target.name.strip().casefold() == identity["name"].casefold()
        and bool(target.is_active) is identity["is_active"]
    )


def dry_run_associations(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> AssociationDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumAssociationMigrationError(
            "Migration run is not a Buildium run."
        )
    if not records:
        raise BuildiumAssociationMigrationError(
            "At least one Buildium Association record is required."
        )

    review = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
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
                    "resolution_target_hoa_association_id": None,
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
                    "reason": "Duplicate Buildium Association Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_hoa_association_id": None,
                }
            )
            invalid += 1
            continue
        seen.add(source_id)
        valid_ids.add(source_id)

        warnings = [
            "Association reconciliation creates no HOA association, Property, property membership, owner/contact relationship, dues, board record, notice, reserve movement, bank mapping, or GL history.",
            "Buildium address, reserve, operating-bank, description, year-built, tax and other source fields are not promoted by this identity-only batch.",
        ]

        candidate = (
            db.query(HOAAssociation)
            .filter(
                HOAAssociation.organization_id == run.organization_id,
                func.lower(HOAAssociation.name) == identity["name"].lower(),
                HOAAssociation.is_active.is_(identity["is_active"]),
            )
            .first()
        )
        if candidate is not None:
            warnings.append(
                f"Possible existing target HOA Association match by exact name/status: local association #{candidate.id}; explicit MATCH_EXISTING review is required."
            )
        else:
            warnings.append(
                "No same-organization HOA Association with the exact source name/status was found; this batch does not create HOA associations."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "HOA_ASSOCIATIONS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )

        resolution = review.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = (
            resolution["target_hoa_association_id"] if resolution else None
        )

        if durable is not None:
            if durable.target_entity != "HOA_ASSOCIATION":
                raise BuildiumAssociationMigrationError(
                    "Buildium Association mapping is inconsistent."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumAssociationMigrationError(
                    f"Buildium source Association ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            action = "MATCH_EXISTING"
            target_id = durable.target_id
            warnings.append(
                f"Buildium source Association ID {source_id} is already durably mapped to local HOA Association #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target(db, run=run, target_id=target_id)
            if target is None:
                raise BuildiumAssociationMigrationError(
                    f"Reviewed target HOA Association #{target_id} is not in the target organization."
                )
            if not _identity_matches(target, identity):
                raise BuildiumAssociationMigrationError(
                    "Reviewed HOA Association name/status no longer matches the Buildium source."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local HOA Association #{target.id}; commit creates migration metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Association review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_hoa_association_id": None,
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
                    "name": identity["name"],
                    "source_is_active": identity["is_active"],
                    "target_hoa_association_id": target_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_hoa_association_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(review) - valid_ids, key=int)
    if unknown:
        raise BuildiumAssociationMigrationError(
            "Association review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "HOA_ASSOCIATIONS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "hoa_associations_created": False,
        "hoa_associations_updated": False,
        "properties_created": False,
        "property_memberships_changed": False,
        "owner_or_contact_relationships_changed": False,
        "dues_or_assessments_created": False,
        "reserve_or_bank_mapping_created": False,
        "gl_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return AssociationDryRunResult(
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


def commit_associations(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> AssociationCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumAssociationMigrationError(
            "Commit payload, review state, or reviewed target snapshot does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumAssociationMigrationError(
            "Commit requires the exact latest successful Buildium Association dry run."
        )

    preview = dry_run_associations(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumAssociationMigrationError(
            "Association commit is blocked while the dry run contains invalid records."
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
                PlatformMigrationItem.resource == "HOA_ASSOCIATIONS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            raise BuildiumAssociationMigrationError(
                "Association controlled mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row."
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
                PlatformMigrationItem.resource == "HOA_ASSOCIATIONS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )

        if prior is not None:
            if prior.target_entity != "HOA_ASSOCIATION":
                raise BuildiumAssociationMigrationError(
                    "Buildium Association mapping is inconsistent."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_hoa_association_id": prior.target_id,
                    "replayed": True,
                }
            )
            continue

        target_id = review[source_id]["target_hoa_association_id"]
        target = _target(db, run=run, target_id=target_id)
        if target is None:
            raise BuildiumAssociationMigrationError(
                f"Reviewed target HOA Association #{target_id} is no longer available."
            )
        if not _identity_matches(target, row["mapped"]):
            raise BuildiumAssociationMigrationError(
                "Reviewed target HOA Association changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="HOA_ASSOCIATIONS",
                source_id=source_id,
                target_entity="HOA_ASSOCIATION",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_hoa_association_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "HOA_ASSOCIATIONS_MAPPED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "HOA_ASSOCIATIONS_REVIEWED"
        db.flush()
        review_recorded = True

    return AssociationCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        matched_existing=matched,
        skipped_review=preview.skipped_review,
        warning_count=preview.warning_count,
        rows=rows,
    )
