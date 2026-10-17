"""Buildium rental-owner/property relationship reconciliation for Phase 4.14.

Buildium Rental Owner resources explicitly carry PropertyIds. This adapter uses
that source association only to reconcile an already-existing target
PropertyOwner row after the owner and property identities have both been
durably mapped in the same migration run.

Buildium PropertyIds do not carry ownership percentage or primary-owner
semantics. This module therefore never creates or updates PropertyOwner rows,
never changes Property.owner_id/ownership_pct, and never imports tax data.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, PropertyOwner
from app.models.user import User, UserRole


class BuildiumOwnerPropertyMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class OwnerPropertyDryRunResult:
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
class OwnerPropertyCommitResult:
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


def _property_ids(value: Any) -> tuple[list[str], str | None]:
    if not isinstance(value, list) or not value:
        return [], "PropertyIds must contain at least one positive Buildium Property ID."
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        source_id = _positive_id(raw)
        if source_id is None:
            return [], "PropertyIds must contain only positive Buildium Property IDs."
        if source_id in seen:
            return [], "PropertyIds contains a duplicate Buildium Property ID."
        seen.add(source_id)
        result.append(source_id)
    return result, None


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
        raise BuildiumOwnerPropertyMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _pair_key(owner_source_id: str, property_source_id: str) -> str:
    return f"{owner_source_id}:{property_source_id}"


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        owner_id = _positive_id(item.get("source_owner_id"))
        property_id = _positive_id(item.get("source_property_id"))
        if owner_id is None or property_id is None:
            raise BuildiumOwnerPropertyMigrationError(
                "Owner/property review requires positive source_owner_id and source_property_id."
            )
        key = _pair_key(owner_id, property_id)
        if key in result:
            raise BuildiumOwnerPropertyMigrationError(
                f"Duplicate Owner/property review decision for source relationship {key}."
            )
        action = str(item.get("action") or "").strip()
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumOwnerPropertyMigrationError(
                "Owner/property review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_property_owner_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumOwnerPropertyMigrationError(
                    "MATCH_EXISTING requires a positive target PropertyOwner ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumOwnerPropertyMigrationError(
                    "MATCH_EXISTING requires a positive target PropertyOwner ID."
                )
            if target < 1:
                raise BuildiumOwnerPropertyMigrationError(
                    "MATCH_EXISTING requires a positive target PropertyOwner ID."
                )
        elif target is not None:
            raise BuildiumOwnerPropertyMigrationError(
                "target_property_owner_id is only valid for MATCH_EXISTING."
            )
        result[key] = {
            "source_owner_id": int(owner_id),
            "source_property_id": int(property_id),
            "action": action,
            "target_property_owner_id": target,
        }
    return result


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        owner_source_id = _positive_id(record.get("Id"))
        property_ids, error = _property_ids(record.get("PropertyIds"))
        if error is not None:
            property_ids = []
        owner_mapping = (
            _mapping(
                db,
                run=run,
                resource="OWNERS",
                source_id=owner_source_id,
                target_entity="OWNER_USER",
            )
            if owner_source_id is not None
            else None
        )
        for property_source_id in property_ids:
            property_mapping = _mapping(
                db,
                run=run,
                resource="PROPERTIES",
                source_id=property_source_id,
                target_entity="PROPERTY",
            )
            relationship = None
            if owner_mapping is not None and property_mapping is not None:
                relationship = (
                    db.query(PropertyOwner)
                    .filter(
                        PropertyOwner.organization_id == run.organization_id,
                        PropertyOwner.property_id == property_mapping.target_id,
                        PropertyOwner.user_id == owner_mapping.target_id,
                    )
                    .first()
                )
            result.append(
                {
                    "source_relationship": _pair_key(owner_source_id or "0", property_source_id),
                    "owner": (
                        {
                            "target_id": owner_mapping.target_id,
                            "source_fingerprint": owner_mapping.source_fingerprint,
                        }
                        if owner_mapping is not None
                        else None
                    ),
                    "property": (
                        {
                            "target_id": property_mapping.target_id,
                            "source_fingerprint": property_mapping.source_fingerprint,
                        }
                        if property_mapping is not None
                        else None
                    ),
                    "target_relationship": (
                        {
                            "id": relationship.id,
                            "ownership_pct": str(relationship.ownership_pct),
                            "is_primary": bool(relationship.is_primary),
                            "is_active": bool(relationship.is_active),
                            "deleted": relationship.deleted_at is not None,
                        }
                        if relationship is not None
                        else None
                    ),
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
    resolution_map = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "OWNER_PROPERTY_RELATIONSHIPS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [resolution_map[key] for key in sorted(resolution_map)],
        "dependency_mappings": _dependency_snapshot(db, run=run, records=records),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _target_relationship(
    db: Session,
    *,
    run: PlatformMigrationRun,
    relationship_id: int,
) -> PropertyOwner | None:
    return (
        db.query(PropertyOwner)
        .join(Property, Property.id == PropertyOwner.property_id)
        .join(User, User.id == PropertyOwner.user_id)
        .filter(
            PropertyOwner.id == relationship_id,
            PropertyOwner.organization_id == run.organization_id,
            Property.organization_id == run.organization_id,
            User.organization_id == run.organization_id,
            User.role == UserRole.OWNER,
            PropertyOwner.is_active.is_(True),
            PropertyOwner.deleted_at.is_(None),
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )


def dry_run_owner_property_relationships(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> OwnerPropertyDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumOwnerPropertyMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumOwnerPropertyMigrationError(
            "At least one Buildium Rental Owner record is required."
        )

    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen_owners: set[str] = set()
    seen_pairs: set[str] = set()
    reviewable = skipped_review = invalid = warning_count = 0

    for record in records:
        owner_source_id = _positive_id(record.get("Id"))
        if owner_source_id is None:
            rows.append({
                "source_owner_id": None,
                "source_property_id": None,
                "source_relationship": None,
                "reviewable": False,
                "reason": "Buildium Rental Owner Id must be a positive integer.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        if owner_source_id in seen_owners:
            rows.append({
                "source_owner_id": owner_source_id,
                "source_property_id": None,
                "source_relationship": None,
                "reviewable": False,
                "reason": "Duplicate Buildium Rental Owner Id in this dry run.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        seen_owners.add(owner_source_id)

        property_ids, property_error = _property_ids(record.get("PropertyIds"))
        if property_error is not None:
            rows.append({
                "source_owner_id": owner_source_id,
                "source_property_id": None,
                "source_relationship": None,
                "reviewable": False,
                "reason": property_error,
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue

        owner_mapping = _mapping(
            db,
            run=run,
            resource="OWNERS",
            source_id=owner_source_id,
            target_entity="OWNER_USER",
        )
        if owner_mapping is None:
            for property_source_id in property_ids:
                rows.append({
                    "source_owner_id": owner_source_id,
                    "source_property_id": property_source_id,
                    "source_relationship": _pair_key(owner_source_id, property_source_id),
                    "reviewable": False,
                    "reason": f"Owner/property reconciliation requires durable Buildium Owner mapping {owner_source_id}.",
                    "mapped": None,
                    "warnings": [],
                })
                invalid += 1
            continue
        owner = (
            db.query(User)
            .filter(
                User.id == owner_mapping.target_id,
                User.organization_id == run.organization_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )
        if owner is None:
            for property_source_id in property_ids:
                rows.append({
                    "source_owner_id": owner_source_id,
                    "source_property_id": property_source_id,
                    "source_relationship": _pair_key(owner_source_id, property_source_id),
                    "reviewable": False,
                    "reason": "Mapped Buildium Owner is no longer an active OWNER in organization scope.",
                    "mapped": None,
                    "warnings": [],
                })
                invalid += 1
            continue

        for property_source_id in property_ids:
            pair = _pair_key(owner_source_id, property_source_id)
            if pair in seen_pairs:
                raise BuildiumOwnerPropertyMigrationError(
                    f"Duplicate Buildium owner/property relationship {pair}."
                )
            seen_pairs.add(pair)
            property_mapping = _mapping(
                db,
                run=run,
                resource="PROPERTIES",
                source_id=property_source_id,
                target_entity="PROPERTY",
            )
            if property_mapping is None:
                rows.append({
                    "source_owner_id": owner_source_id,
                    "source_property_id": property_source_id,
                    "source_relationship": pair,
                    "reviewable": False,
                    "reason": f"Owner/property reconciliation requires durable Buildium Property mapping {property_source_id}.",
                    "mapped": None,
                    "warnings": [],
                })
                invalid += 1
                continue
            prop = (
                db.query(Property)
                .filter(
                    Property.id == property_mapping.target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if prop is None:
                rows.append({
                    "source_owner_id": owner_source_id,
                    "source_property_id": property_source_id,
                    "source_relationship": pair,
                    "reviewable": False,
                    "reason": "Mapped Buildium Property is no longer active in organization scope.",
                    "mapped": None,
                    "warnings": [],
                })
                invalid += 1
                continue

            relationship = (
                db.query(PropertyOwner)
                .filter(
                    PropertyOwner.organization_id == run.organization_id,
                    PropertyOwner.property_id == prop.id,
                    PropertyOwner.user_id == owner.id,
                    PropertyOwner.is_active.is_(True),
                    PropertyOwner.deleted_at.is_(None),
                )
                .first()
            )
            warnings = [
                "Buildium PropertyIds prove an owner/property association but do not provide ownership percentage or primary-owner semantics.",
                "This batch never creates or updates PropertyOwner, Property.owner_id, Property.ownership_pct, tax profiles, 1099 settings, or financial history.",
            ]
            candidate_id = relationship.id if relationship is not None else None
            if relationship is None:
                warnings.append(
                    "No active target PropertyOwner relationship exists for the mapped owner/property pair; this batch does not create one."
                )
            else:
                warnings.append(
                    f"Exact existing target PropertyOwner relationship candidate #{relationship.id}; explicit MATCH_EXISTING review is required."
                )

            durable = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "BUILDIUM",
                    PlatformMigrationItem.resource == "OWNER_PROPERTY_RELATIONSHIPS",
                    PlatformMigrationItem.source_id == pair,
                )
                .first()
            )
            resolution = resolution_map.get(pair)
            action = resolution["action"] if resolution else None
            target_id = resolution["target_property_owner_id"] if resolution else None
            if durable is not None:
                if durable.target_entity != "PROPERTY_OWNER_RELATIONSHIP":
                    raise BuildiumOwnerPropertyMigrationError(
                        "Buildium owner/property mapping is inconsistent."
                    )
                if resolution is not None and (
                    action != "MATCH_EXISTING" or target_id != durable.target_id
                ):
                    raise BuildiumOwnerPropertyMigrationError(
                        f"Buildium owner/property relationship {pair} is already durably mapped and cannot be re-resolved."
                    )
                target = _target_relationship(db, run=run, relationship_id=durable.target_id)
                if target is None or target.property_id != prop.id or target.user_id != owner.id:
                    raise BuildiumOwnerPropertyMigrationError(
                        "Previously mapped PropertyOwner relationship is missing, inactive, deleted, or no longer matches the source pair."
                    )
                warnings.append(
                    f"Relationship {pair} is already durably mapped to PropertyOwner #{target.id}; commit will replay."
                )

            if action == "MATCH_EXISTING":
                target = _target_relationship(db, run=run, relationship_id=target_id)
                if target is None:
                    raise BuildiumOwnerPropertyMigrationError(
                        f"Reviewed PropertyOwner #{target_id} is not active in the target organization."
                    )
                if target.property_id != prop.id or target.user_id != owner.id:
                    raise BuildiumOwnerPropertyMigrationError(
                        "Reviewed PropertyOwner does not match the current durable Buildium Owner and Property mappings."
                    )
                warnings.append(
                    f"Reviewed MATCH_EXISTING target: PropertyOwner #{target.id}; percentage and primary flag remain untouched."
                )
            elif action == "SKIP":
                rows.append({
                    "source_owner_id": owner_source_id,
                    "source_property_id": property_source_id,
                    "source_relationship": pair,
                    "reviewable": False,
                    "reason": "Explicitly skipped after owner/property relationship review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_property_owner_id": None,
                })
                skipped_review += 1
                warning_count += len(warnings)
                continue

            rows.append({
                "source_owner_id": owner_source_id,
                "source_property_id": property_source_id,
                "source_relationship": pair,
                "reviewable": relationship is not None,
                "reason": None if relationship is not None else "No existing target PropertyOwner relationship is available to map.",
                "mapped": {
                    "target_owner_user_id": owner.id,
                    "target_property_id": prop.id,
                    "candidate_property_owner_id": candidate_id,
                    "ownership_percentage_from_source": False,
                    "primary_owner_from_source": False,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_property_owner_id": target_id,
            })
            if relationship is not None:
                reviewable += 1
            else:
                invalid += 1
            warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - seen_pairs)
    if unknown:
        raise BuildiumOwnerPropertyMigrationError(
            "Owner/property review contains relationships not present in this dry run: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "OWNER_PROPERTY_RELATIONSHIPS",
        "total": len(rows),
        "reviewable": reviewable,
        "skipped_review": skipped_review,
        "invalid": invalid,
        "warning_count": warning_count,
        "target_mutation": False,
        "ownership_percentage_imported": False,
        "primary_owner_imported": False,
        "tax_information_imported": False,
    }
    run.last_dry_run_fingerprint = fingerprint
    run.last_dry_run_summary = summary
    run.status = "DRY_RUN_READY"
    db.flush()
    return OwnerPropertyDryRunResult(
        fingerprint, replayed, len(rows), reviewable, skipped_review,
        invalid, warning_count, rows, summary
    )


def commit_owner_property_relationships(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> OwnerPropertyCommitResult:
    preview = dry_run_owner_property_relationships(
        db, run=run, records=records, resolutions=resolutions
    )
    if preview.fingerprint != expected_fingerprint:
        raise BuildiumOwnerPropertyMigrationError(
            "Buildium owner/property dry run is stale; run review again before commit."
        )
    if preview.invalid:
        raise BuildiumOwnerPropertyMigrationError(
            "Buildium owner/property commit is blocked while missing or unsupported target relationships remain."
        )

    resolution_map = _normalize_resolutions(resolutions)
    valid = [row for row in preview.rows if row["mapped"] is not None]
    missing: list[str] = []
    for row in valid:
        pair = row["source_relationship"]
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "OWNER_PROPERTY_RELATIONSHIPS",
                PlatformMigrationItem.source_id == pair,
            )
            .first()
        )
        if prior is None and (
            pair not in resolution_map
            or resolution_map[pair]["action"] != "MATCH_EXISTING"
        ):
            missing.append(pair)
    if missing:
        raise BuildiumOwnerPropertyMigrationError(
            "Owner/property relationship mapping requires explicit MATCH_EXISTING review for every supported relationship: "
            + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False
    for row in valid:
        pair = row["source_relationship"]
        mapped = row["mapped"]
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "OWNER_PROPERTY_RELATIONSHIPS",
                PlatformMigrationItem.source_id == pair,
            )
            .first()
        )
        if prior is not None:
            target = _target_relationship(db, run=run, relationship_id=prior.target_id)
            if (
                target is None
                or target.user_id != mapped["target_owner_user_id"]
                or target.property_id != mapped["target_property_id"]
            ):
                raise BuildiumOwnerPropertyMigrationError(
                    "Previously mapped PropertyOwner relationship changed after dry run."
                )
            rows.append({
                "source_relationship": pair,
                "target_property_owner_id": target.id,
                "replayed": True,
            })
            continue

        target_id = resolution_map[pair]["target_property_owner_id"]
        target = _target_relationship(db, run=run, relationship_id=target_id)
        if (
            target is None
            or target.user_id != mapped["target_owner_user_id"]
            or target.property_id != mapped["target_property_id"]
        ):
            raise BuildiumOwnerPropertyMigrationError(
                "Reviewed PropertyOwner relationship changed after dry run."
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="OWNER_PROPERTY_RELATIONSHIPS",
                source_id=pair,
                target_entity="PROPERTY_OWNER_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_relationship": pair,
            "target_property_owner_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "OWNER_PROPERTIES_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "OWNER_PROPERTIES_REVIEWED"
        db.flush()
        review_recorded = True

    return OwnerPropertyCommitResult(
        preview.fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
