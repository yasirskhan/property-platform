"""Safe Buildium Property Group reconciliation for Phase 4.14.

Maps only an already-existing target PropertyGroup whose name and current
membership exactly match the Buildium source after every source Property has a
durable same-run Buildium mapping. Target groups/memberships are never mutated.
"""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property
from app.models.property_group import PropertyGroup, PropertyGroupMembership


class BuildiumPropertyGroupMigrationError(ValueError):
    pass


def _id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return str(number) if number > 0 else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _mapping(db: Session, run: PlatformMigrationRun, resource: str, source_id: str, entity: str):
    row = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "BUILDIUM",
        PlatformMigrationItem.resource == resource,
        PlatformMigrationItem.source_id == source_id,
    ).first()
    if row is not None and row.target_entity != entity:
        raise BuildiumPropertyGroupMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _property_ids(value: Any):
    if not isinstance(value, list):
        return None, "Buildium Property Group Properties must be an explicit list."
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or _id(item.get("Id")) is None:
            return None, "Every Buildium Property Group property requires a positive Id."
        source_id = _id(item.get("Id"))
        if source_id in seen:
            return None, "Buildium Property Group Properties contains a duplicate property Id."
        seen.add(source_id)
        result.append(source_id)
    return sorted(result, key=int), None


def _members(db: Session, run: PlatformMigrationRun, group_id: int) -> list[int]:
    rows = db.query(PropertyGroupMembership.property_id).join(
        Property, Property.id == PropertyGroupMembership.property_id
    ).filter(
        PropertyGroupMembership.organization_id == run.organization_id,
        PropertyGroupMembership.group_id == group_id,
        Property.organization_id == run.organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).order_by(PropertyGroupMembership.property_id).all()
    return [int(row[0]) for row in rows]


def _group(db: Session, run: PlatformMigrationRun, group_id: int):
    return db.query(PropertyGroup).filter(
        PropertyGroup.id == group_id,
        PropertyGroup.organization_id == run.organization_id,
    ).first()


def _resolutions(items):
    output = {}
    for item in items or []:
        source_id = _id(item.get("source_id"))
        if source_id is None or source_id in output:
            raise BuildiumPropertyGroupMigrationError("Property Group review requires unique positive source_id values.")
        action = _text(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumPropertyGroupMigrationError("Property Group review supports only MATCH_EXISTING or SKIP.")
        target = item.get("target_property_group_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumPropertyGroupMigrationError("MATCH_EXISTING requires a positive target Property Group ID.")
            try:
                target = int(target)
            except (TypeError, ValueError):
                target = 0
            if target < 1:
                raise BuildiumPropertyGroupMigrationError("MATCH_EXISTING requires a positive target Property Group ID.")
        elif target is not None:
            raise BuildiumPropertyGroupMigrationError("target_property_group_id is only valid for MATCH_EXISTING.")
        output[source_id] = {"source_id": int(source_id), "action": action, "target_property_group_id": target}
    return output


def _mapped(db: Session, run: PlatformMigrationRun, record: dict[str, Any]):
    source_id = _id(record.get("Id"))
    name = _text(record.get("Name"))
    if source_id is None:
        return None, "Buildium Property Group Id must be a positive integer.", []
    if not name:
        return None, "Buildium Property Group Name is required.", []
    if len(name) > 100:
        return None, "Buildium Property Group Name exceeds the target 100-character limit.", []
    source_properties, error = _property_ids(record.get("Properties"))
    if error:
        return None, error, []
    targets, deps = [], []
    for property_source_id in source_properties:
        mapping = _mapping(db, run, "PROPERTIES", property_source_id, "PROPERTY")
        if mapping is None:
            return None, f"Property Group reconciliation requires durable Buildium Property mapping {property_source_id}.", []
        prop = db.query(Property).filter(
            Property.id == mapping.target_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        ).first()
        if prop is None:
            return None, "Mapped Buildium Property is no longer active and in organization scope.", []
        targets.append(prop.id)
        deps.append({"source_id": property_source_id, "target_id": prop.id, "source_fingerprint": mapping.source_fingerprint})
    targets.sort()
    candidate = db.query(PropertyGroup).filter(
        PropertyGroup.organization_id == run.organization_id,
        PropertyGroup.name_key == name.casefold(),
    ).first()
    warnings, candidate_id = [], None
    if candidate is None:
        warnings.append("No existing same-name Property Group is available; this bounded batch does not create groups.")
    elif _members(db, run, candidate.id) != targets:
        warnings.append("Existing same-name Property Group membership differs from Buildium; MATCH_EXISTING is blocked until memberships already match.")
    else:
        candidate_id = candidate.id
        if (candidate.description or "").strip() != (_text(record.get("Description")) or ""):
            warnings.append("Target Property Group description differs from Buildium; migration will not overwrite it.")
    return {
        "source_id": source_id,
        "name": name,
        "source_property_ids": source_properties,
        "target_property_ids": targets,
        "property_dependencies": deps,
        "candidate_property_group_id": candidate_id,
    }, None, warnings


def _match_reason(db: Session, run: PlatformMigrationRun, group_id: int, mapped: dict[str, Any]):
    group = _group(db, run, group_id)
    if group is None:
        return "Target Property Group is not in the migration organization."
    if group.name != mapped["name"] or group.name_key != mapped["name"].casefold():
        return "Target Property Group name does not exactly match Buildium."
    if _members(db, run, group.id) != mapped["target_property_ids"]:
        return "Target Property Group membership does not exactly match mapped Buildium properties."
    return None


def _fingerprint(db: Session, run: PlatformMigrationRun, records, resolutions):
    review = _resolutions(resolutions)
    dependencies, targets = [], []
    for record in records:
        source_properties, error = _property_ids(record.get("Properties"))
        deps = []
        if not error:
            for source_id in source_properties:
                mapping = _mapping(db, run, "PROPERTIES", source_id, "PROPERTY")
                deps.append({"source_id": source_id, "target_id": mapping.target_id if mapping else None,
                              "source_fingerprint": mapping.source_fingerprint if mapping else None})
        dependencies.append({"source_id": _id(record.get("Id")), "properties": deps})
    for key in sorted(review, key=int):
        item = review[key]
        if item["action"] == "MATCH_EXISTING":
            group = _group(db, run, item["target_property_group_id"])
            targets.append({"id": item["target_property_group_id"], "name": group.name if group else None,
                            "name_key": group.name_key if group else None,
                            "property_ids": _members(db, run, group.id) if group else None})
    payload = {"provider": "BUILDIUM", "resource": "PROPERTY_GROUPS",
               "organization_id": run.organization_id, "source_account_ref": run.source_account_ref,
               "records": records, "resolutions": [review[k] for k in sorted(review, key=int)],
               "dependencies": dependencies, "targets": targets}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def dry_run_property_groups(db: Session, *, run: PlatformMigrationRun, records, resolutions=None):
    if run.provider != "BUILDIUM" or not records:
        raise BuildiumPropertyGroupMigrationError("A Buildium run with at least one Property Group record is required.")
    review, rows, seen = _resolutions(resolutions), [], set()
    reviewable = skipped = invalid = warnings_total = 0
    fingerprint = _fingerprint(db, run, records, resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    for record in records:
        source_id = _id(record.get("Id"))
        if source_id and source_id in seen:
            rows.append({"source_id": source_id, "reviewable": False, "reason": "Duplicate Buildium Property Group Id in this dry run.", "mapped": None, "warnings": []})
            invalid += 1
            continue
        if source_id:
            seen.add(source_id)
        mapped, reason, warnings = _mapped(db, run, record)
        warnings_total += len(warnings)
        if mapped is None:
            rows.append({"source_id": source_id, "reviewable": False, "reason": reason, "mapped": None, "warnings": warnings})
            invalid += 1
            continue
        prior = _mapping(db, run, "PROPERTY_GROUPS", mapped["source_id"], "PROPERTY_GROUP")
        resolution = review.get(mapped["source_id"])
        target_id = prior.target_id if prior else (resolution.get("target_property_group_id") if resolution and resolution["action"] == "MATCH_EXISTING" else None)
        if target_id is not None:
            mismatch = _match_reason(db, run, target_id, mapped)
            if mismatch:
                if prior:
                    rows.append({"source_id": mapped["source_id"], "reviewable": False, "reason": "Previously mapped Property Group changed: " + mismatch, "mapped": mapped, "warnings": warnings})
                    invalid += 1
                    continue
                raise BuildiumPropertyGroupMigrationError(mismatch)
            mapped["candidate_property_group_id"] = target_id
        if resolution and resolution["action"] == "SKIP":
            skipped += 1
        reviewable += 1
        rows.append({"source_id": mapped["source_id"], "reviewable": True, "reason": None, "mapped": mapped, "warnings": warnings,
                     "resolution_action": resolution["action"] if resolution else None,
                     "resolution_target_property_group_id": resolution.get("target_property_group_id") if resolution else None})
    summary = {"total": len(records), "reviewable": reviewable, "skipped_review": skipped, "invalid": invalid,
               "warning_count": warnings_total, "target_groups_created": False, "target_groups_updated": False,
               "target_memberships_changed": False}
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.status = "PROPERTY_GROUPS_DRY_RUN_READY"
        db.flush()
    return SimpleNamespace(fingerprint=fingerprint, replayed=replayed, total=len(records), reviewable=reviewable,
                           skipped_review=skipped, invalid=invalid, warning_count=warnings_total, rows=rows, summary=summary)


def commit_property_groups(db: Session, *, run: PlatformMigrationRun, records, expected_fingerprint: str,
                           platform_user_id: int, resolutions=None):
    preview = dry_run_property_groups(db, run=run, records=records, resolutions=resolutions)
    if preview.fingerprint != expected_fingerprint:
        raise BuildiumPropertyGroupMigrationError("Buildium Property Group dry run is stale; run review again before commit.")
    if preview.invalid:
        raise BuildiumPropertyGroupMigrationError("Buildium Property Group commit is blocked while invalid relationships remain.")
    review = _resolutions(resolutions)
    missing = [row["source_id"] for row in preview.rows
               if _mapping(db, run, "PROPERTY_GROUPS", row["source_id"], "PROPERTY_GROUP") is None and row["source_id"] not in review]
    if missing:
        raise BuildiumPropertyGroupMigrationError("Property Group mapping requires explicit MATCH_EXISTING or SKIP review: " + ", ".join(missing))
    rows, matched, skipped, changed = [], 0, 0, False
    for row in preview.rows:
        source_id, mapped = row["source_id"], row["mapped"]
        prior = _mapping(db, run, "PROPERTY_GROUPS", source_id, "PROPERTY_GROUP")
        if prior:
            if _match_reason(db, run, prior.target_id, mapped):
                raise BuildiumPropertyGroupMigrationError("Previously mapped Property Group changed after dry run.")
            rows.append({"source_id": source_id, "target_property_group_id": prior.target_id, "replayed": True})
            continue
        resolution = review[source_id]
        if resolution["action"] == "SKIP":
            skipped += 1
            continue
        target_id = resolution["target_property_group_id"]
        mismatch = _match_reason(db, run, target_id, mapped)
        if mismatch:
            raise BuildiumPropertyGroupMigrationError("Reviewed Property Group changed after dry run: " + mismatch)
        db.add(PlatformMigrationItem(run_id=run.id, organization_id=run.organization_id, provider="BUILDIUM",
                                     resource="PROPERTY_GROUPS", source_id=source_id, target_entity="PROPERTY_GROUP",
                                     target_id=target_id, source_fingerprint=preview.fingerprint,
                                     created_by_platform_user_id=platform_user_id))
        rows.append({"source_id": source_id, "target_property_group_id": target_id, "replayed": False})
        matched += 1
        changed = True
    review_recorded = False
    if changed:
        run.status = "PROPERTY_GROUPS_RECONCILED"
        db.flush()
    elif skipped and not rows:
        run.status = "PROPERTY_GROUPS_REVIEWED"
        db.flush()
        review_recorded = True
    return SimpleNamespace(fingerprint=preview.fingerprint, replayed=not changed and not review_recorded,
                           matched_existing=matched, skipped_review=skipped, warning_count=preview.warning_count, rows=rows)
