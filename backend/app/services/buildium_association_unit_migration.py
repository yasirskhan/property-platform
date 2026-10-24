"""Buildium Association Unit existing-target reconciliation for Phase 4.14.

A Buildium association unit may be reconciled only to an already-existing
same-organization Unit whose Property already has an explicit
HOAPropertyMembership to the already-mapped Buildium Association.

This batch creates migration metadata only. It never creates or edits a Unit,
Property, HOA association, HOA property membership, owner/tenant relationship,
assessment, reserve, bank mapping, or accounting history.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.hoa_association import HOAAssociation, HOAPropertyMembership
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit


class BuildiumAssociationUnitMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class AssociationUnitDryRunResult:
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
class AssociationUnitCommitResult:
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


def _source_address(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    raw = record.get("Address")
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "Buildium Association Unit Address must be an object when supplied."

    limits = {
        "AddressLine1": 255,
        "AddressLine2": 255,
        "AddressLine3": 255,
        "City": 100,
        "State": 50,
        "PostalCode": 20,
        "Country": 100,
    }
    result: dict[str, Any] = {}
    for key, limit in limits.items():
        value = _clean(raw.get(key))
        if value is not None and len(value) > limit:
            return None, f"Buildium Association Unit Address.{key} exceeds {limit} characters."
        result[key] = value
    return result, None


def _source_identity(
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Association Unit Id must be a positive integer."

    association_id = _positive_id(record.get("AssociationId"))
    if association_id is None:
        return None, "Buildium Association Unit AssociationId must be a positive integer."

    unit_number = _clean(record.get("UnitNumber"))
    if unit_number is None:
        return None, "Buildium Association Unit UnitNumber is required."
    if len(unit_number) > 50:
        return None, "Buildium Association Unit UnitNumber exceeds the target 50-character limit."

    association_name = _clean(record.get("AssociationName"))
    if association_name is not None and len(association_name) > 160:
        return None, "Buildium Association Unit AssociationName exceeds 160 characters."

    address, address_error = _source_address(record)
    if address_error:
        return None, address_error

    return {
        "source_id": source_id,
        "association_id": association_id,
        "association_name": association_name,
        "unit_number": unit_number,
        "address": address,
    }, None


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumAssociationUnitMigrationError(
                "Association Unit review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumAssociationUnitMigrationError(
                f"Duplicate Association Unit review decision for source ID {source_id}."
            )

        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumAssociationUnitMigrationError(
                "Association Unit review supports only MATCH_EXISTING or SKIP."
            )

        target_id = item.get("target_unit_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumAssociationUnitMigrationError(
                    "MATCH_EXISTING requires a positive target_unit_id."
                )
        elif target_id is not None:
            raise BuildiumAssociationUnitMigrationError(
                "target_unit_id is only valid for MATCH_EXISTING."
            )

        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_unit_id": target_id,
        }
    return result


def _association_dependency(
    db: Session,
    *,
    run: PlatformMigrationRun,
    source_association_id: str,
) -> tuple[PlatformMigrationItem | None, HOAAssociation | None]:
    mapping = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == "HOA_ASSOCIATIONS",
            PlatformMigrationItem.source_id == source_association_id,
        )
        .first()
    )
    if mapping is None or mapping.target_entity != "HOA_ASSOCIATION":
        return mapping, None

    target = (
        db.query(HOAAssociation)
        .filter(
            HOAAssociation.id == mapping.target_id,
            HOAAssociation.organization_id == run.organization_id,
        )
        .first()
    )
    return mapping, target


def _association_dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    source_association_id: str,
) -> dict[str, Any] | None:
    mapping, target = _association_dependency(
        db,
        run=run,
        source_association_id=source_association_id,
    )
    if mapping is None:
        return None
    return {
        "mapping_id": mapping.id,
        "target_entity": mapping.target_entity,
        "target_id": mapping.target_id,
        "source_fingerprint": mapping.source_fingerprint,
        "target": (
            {
                "id": target.id,
                "name": target.name,
                "name_key": target.name_key,
                "is_active": bool(target.is_active),
            }
            if target is not None
            else None
        ),
    }


def _target(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_unit_id: int,
    target_association_id: int,
) -> tuple[Unit | None, Property | None, HOAPropertyMembership | None]:
    row = (
        db.query(Unit, Property, HOAPropertyMembership)
        .join(Property, Property.id == Unit.property_id)
        .join(
            HOAPropertyMembership,
            HOAPropertyMembership.property_id == Property.id,
        )
        .filter(
            Unit.id == target_unit_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
            HOAPropertyMembership.organization_id == run.organization_id,
            HOAPropertyMembership.association_id == target_association_id,
        )
        .first()
    )
    if row is None:
        return None, None, None
    return row[0], row[1], row[2]


def _target_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_unit_id: int,
    target_association_id: int,
) -> dict[str, Any] | None:
    unit, prop, membership = _target(
        db,
        run=run,
        target_unit_id=target_unit_id,
        target_association_id=target_association_id,
    )
    if unit is None or prop is None or membership is None:
        return None
    return {
        "unit": {
            "id": unit.id,
            "unit_number": unit.unit_number,
            "property_id": unit.property_id,
            "is_active": bool(unit.is_active),
            "deleted_at": unit.deleted_at.isoformat() if unit.deleted_at else None,
        },
        "property": {
            "id": prop.id,
            "name": prop.name,
            "address_line1": prop.address_line1,
            "city": prop.city,
            "state": prop.state,
            "zip_code": prop.zip_code,
            "is_active": bool(prop.is_active),
            "deleted_at": prop.deleted_at.isoformat() if prop.deleted_at else None,
        },
        "membership": {
            "id": membership.id,
            "organization_id": membership.organization_id,
            "association_id": membership.association_id,
            "property_id": membership.property_id,
        },
    }


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    review = _normalize_resolutions(resolutions)

    association_ids = sorted(
        {
            source_id
            for record in records
            if (source_id := _positive_id(record.get("AssociationId"))) is not None
        },
        key=int,
    )
    association_dependencies = {
        source_id: _association_dependency_snapshot(
            db,
            run=run,
            source_association_id=source_id,
        )
        for source_id in association_ids
    }

    target_snapshots: dict[str, Any] = {}
    for source_id, item in review.items():
        if item["action"] != "MATCH_EXISTING":
            continue
        source_record = next(
            (
                record
                for record in records
                if _positive_id(record.get("Id")) == source_id
            ),
            None,
        )
        source_association_id = (
            _positive_id(source_record.get("AssociationId"))
            if source_record is not None
            else None
        )
        dependency = (
            association_dependencies.get(source_association_id)
            if source_association_id is not None
            else None
        )
        target_association_id = (
            dependency.get("target_id")
            if isinstance(dependency, dict)
            and dependency.get("target_entity") == "HOA_ASSOCIATION"
            else None
        )
        target_snapshots[source_id] = (
            _target_snapshot(
                db,
                run=run,
                target_unit_id=item["target_unit_id"],
                target_association_id=target_association_id,
            )
            if target_association_id is not None
            else None
        )

    payload = {
        "provider": "BUILDIUM",
        "resource": "HOA_UNITS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "association_dependencies": association_dependencies,
        "target_snapshots": target_snapshots,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _target_matches(
    unit: Unit,
    identity: dict[str, Any],
) -> bool:
    return unit.unit_number.strip().casefold() == identity["unit_number"].casefold()


def dry_run_association_units(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> AssociationUnitDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumAssociationUnitMigrationError(
            "Migration run is not a Buildium run."
        )
    if not records:
        raise BuildiumAssociationUnitMigrationError(
            "At least one Buildium Association Unit record is required."
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
                    "resolution_target_unit_id": None,
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
                    "reason": "Duplicate Buildium Association Unit Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_unit_id": None,
                }
            )
            invalid += 1
            continue
        seen.add(source_id)

        association_mapping, association = _association_dependency(
            db,
            run=run,
            source_association_id=identity["association_id"],
        )
        if association_mapping is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": (
                        "Referenced Buildium AssociationId has no durable same-run "
                        "HOA Association mapping."
                    ),
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_unit_id": None,
                }
            )
            invalid += 1
            continue
        if association_mapping.target_entity != "HOA_ASSOCIATION" or association is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Referenced Buildium Association mapping is inconsistent.",
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_unit_id": None,
                }
            )
            invalid += 1
            continue
        if (
            identity["association_name"] is not None
            and identity["association_name"].casefold() != association.name.strip().casefold()
        ):
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": (
                        "Buildium AssociationName does not match the already-mapped "
                        "target HOA Association."
                    ),
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                    "resolution_target_unit_id": None,
                }
            )
            invalid += 1
            continue

        valid_ids.add(source_id)
        warnings = [
            "Association Unit reconciliation creates no Unit, Property or HOA property membership; an existing membership is required before MATCH_EXISTING can succeed.",
            "Buildium Association Unit address, size, bedrooms and bathrooms are source evidence only and are not promoted to target Unit fields by this batch.",
            "This mapping does not establish ownership, tenant occupancy, dues liability, board rights, reserve accounting or bank relationships.",
        ]

        candidates = (
            db.query(Unit)
            .join(Property, Property.id == Unit.property_id)
            .join(
                HOAPropertyMembership,
                HOAPropertyMembership.property_id == Property.id,
            )
            .filter(
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
                Unit.is_active.is_(True),
                Unit.deleted_at.is_(None),
                HOAPropertyMembership.organization_id == run.organization_id,
                HOAPropertyMembership.association_id == association.id,
                func.lower(Unit.unit_number) == identity["unit_number"].lower(),
            )
            .order_by(Unit.id.asc())
            .limit(3)
            .all()
        )
        if len(candidates) == 1:
            warnings.append(
                f"Possible existing target HOA-linked Unit match by exact unit number: local Unit #{candidates[0].id}; explicit MATCH_EXISTING review is required."
            )
        elif len(candidates) > 1:
            warnings.append(
                "Multiple existing HOA-linked Units share this unit number; explicit review must select the correct target."
            )
        else:
            warnings.append(
                "No active same-organization Unit with this exact unit number exists under a Property already linked to the mapped HOA Association."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "HOA_UNITS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )

        resolution = review.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_unit_id"] if resolution else None

        if durable is not None:
            if durable.target_entity != "HOA_UNIT_RELATIONSHIP":
                raise BuildiumAssociationUnitMigrationError(
                    "Buildium Association Unit mapping is inconsistent."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumAssociationUnitMigrationError(
                    f"Buildium source Association Unit ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            action = "MATCH_EXISTING"
            target_id = durable.target_id
            warnings.append(
                f"Buildium source Association Unit ID {source_id} is already durably mapped to local Unit #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            unit, prop, membership = _target(
                db,
                run=run,
                target_unit_id=target_id,
                target_association_id=association.id,
            )
            if unit is None or prop is None or membership is None:
                raise BuildiumAssociationUnitMigrationError(
                    "Reviewed target Unit is not an active same-organization Unit under a Property already linked to the mapped HOA Association."
                )
            if not _target_matches(unit, identity):
                raise BuildiumAssociationUnitMigrationError(
                    "Reviewed target Unit number no longer matches the Buildium Association Unit source."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Unit #{unit.id} on Property #{prop.id}; commit creates migration metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Association Unit review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_unit_id": None,
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
                    "source_association_id": identity["association_id"],
                    "source_association_name": identity["association_name"],
                    "unit_number": identity["unit_number"],
                    "source_address": identity["address"],
                    "target_hoa_association_id": association.id,
                    "target_unit_id": target_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_unit_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(review) - valid_ids, key=int)
    if unknown:
        raise BuildiumAssociationUnitMigrationError(
            "Association Unit review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "HOA_UNITS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "units_created": False,
        "units_updated": False,
        "properties_created": False,
        "property_memberships_created": False,
        "property_memberships_updated": False,
        "owner_or_tenant_relationships_changed": False,
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

    return AssociationUnitDryRunResult(
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


def commit_association_units(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> AssociationUnitCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumAssociationUnitMigrationError(
            "Commit payload, dependency mapping, review state or reviewed target snapshot does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumAssociationUnitMigrationError(
            "Commit requires the exact latest successful Buildium Association Unit dry run."
        )

    preview = dry_run_association_units(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumAssociationUnitMigrationError(
            "Association Unit commit is blocked while the dry run contains invalid records."
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
                PlatformMigrationItem.resource == "HOA_UNITS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            raise BuildiumAssociationUnitMigrationError(
                "Association Unit controlled mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row."
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
                PlatformMigrationItem.resource == "HOA_UNITS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )

        if prior is not None:
            if prior.target_entity != "HOA_UNIT_RELATIONSHIP":
                raise BuildiumAssociationUnitMigrationError(
                    "Buildium Association Unit mapping is inconsistent."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_unit_id": prior.target_id,
                    "replayed": True,
                }
            )
            continue

        target_id = review[source_id]["target_unit_id"]
        source_association_id = str(row["mapped"]["source_association_id"])
        _, association = _association_dependency(
            db,
            run=run,
            source_association_id=source_association_id,
        )
        if association is None:
            raise BuildiumAssociationUnitMigrationError(
                "Mapped HOA Association dependency is no longer available."
            )

        unit, prop, membership = _target(
            db,
            run=run,
            target_unit_id=target_id,
            target_association_id=association.id,
        )
        if unit is None or prop is None or membership is None:
            raise BuildiumAssociationUnitMigrationError(
                "Reviewed target Unit/HOA property membership changed after dry run."
            )
        if not _target_matches(unit, row["mapped"]):
            raise BuildiumAssociationUnitMigrationError(
                "Reviewed target Unit identity changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="HOA_UNITS",
                source_id=source_id,
                target_entity="HOA_UNIT_RELATIONSHIP",
                target_id=unit.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_unit_id": unit.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "HOA_UNITS_MAPPED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "HOA_UNITS_REVIEWED"
        db.flush()
        review_recorded = True

    return AssociationUnitCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        matched_existing=matched,
        skipped_review=preview.skipped_review,
        warning_count=preview.warning_count,
        rows=rows,
    )
