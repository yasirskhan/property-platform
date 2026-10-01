"""AppFolio migration mapping foundation.

This module intentionally does not perform network calls and does not persist raw
AppFolio payloads. Phase 4.13 uses it to validate/map provider records before a
later verified transport and commit step.

Public AppFolio Stack documentation exposes Property fields including Id, Name,
Address1/2, City, State, Zip, HiddenAt and PropertyType. Authentication and
customer-specific API access remain external prerequisites and are not guessed
here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, PropertyType, Unit
from app.services.plan_limits import PlanUnitLimitExceeded, require_unit_capacity


class AppFolioMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class PropertyDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    skipped_hidden: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _normalized(record: dict[str, Any]) -> dict[str, Any]:
    return {
        re.sub(r"[^a-z0-9]", "", str(key).strip().lower()): value
        for key, value in record.items()
    }


def _value(record: dict[str, Any], *names: str) -> Any:
    normalized = _normalized(record)
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.strip().lower())
        if key in normalized:
            return normalized[key]
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_hidden(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text not in {"", "none", "null", "false", "0"}


def _property_type(value: Any) -> tuple[str, list[str]]:
    raw = (_clean_text(value) or "").lower()
    compact = re.sub(r"[^a-z0-9]", "", raw)
    mappings = {
        "singlefamily": PropertyType.SINGLE_FAMILY.value,
        "singlefamilyhome": PropertyType.SINGLE_FAMILY.value,
        "multifamily": PropertyType.MULTI_FAMILY.value,
        "multifamilyhome": PropertyType.MULTI_FAMILY.value,
        "apartment": PropertyType.APARTMENT.value,
        "apartments": PropertyType.APARTMENT.value,
        "condo": PropertyType.CONDO.value,
        "condominium": PropertyType.CONDO.value,
        "townhouse": PropertyType.TOWNHOUSE.value,
        "townhome": PropertyType.TOWNHOUSE.value,
        "commercial": PropertyType.COMMERCIAL.value,
    }
    if compact in mappings:
        return mappings[compact], []
    if not compact:
        return PropertyType.OTHER.value, [
            "AppFolio PropertyType is not recorded; target preview uses OTHER."
        ]
    return PropertyType.OTHER.value, [
        f"Unrecognized AppFolio PropertyType {value!r}; target preview uses OTHER."
    ]


def _required(
    record: dict[str, Any],
    *,
    field: str,
    aliases: tuple[str, ...],
    max_length: int,
) -> tuple[str | None, str | None]:
    value = _clean_text(_value(record, *aliases))
    if value is None:
        return None, f"{field} is required."
    if len(value) > max_length:
        return None, f"{field} exceeds {max_length} characters."
    return value, None


def _optional(
    record: dict[str, Any],
    *,
    aliases: tuple[str, ...],
    max_length: int,
) -> tuple[str | None, str | None]:
    value = _clean_text(_value(record, *aliases))
    if value is None:
        return None, None
    if len(value) > max_length:
        return None, f"{aliases[0]} exceeds {max_length} characters."
    return value, None


def _fingerprint(
    *,
    organization_id: int,
    source_account_ref: str,
    include_hidden: bool,
    records: list[dict[str, Any]],
    source_context_fingerprint: str | None = None,
) -> str:
    canonical = json.dumps(
        {
            "provider": "APPFOLIO",
            "organization_id": organization_id,
            "source_account_ref": source_account_ref,
            "include_hidden": include_hidden,
            "source_context_fingerprint": source_context_fingerprint,
            "records": records,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dry_run_properties(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_hidden: bool,
    records: list[dict[str, Any]],
    source_context_fingerprint: str | None = None,
) -> PropertyDryRunResult:
    if run.provider != "APPFOLIO":
        raise AppFolioMigrationError("Migration run is not an AppFolio run.")
    resolved_existing_matches = dict(resolved_existing_matches or {})
    force_create_new_source_ids = set(force_create_new_source_ids or set())
    if not records:
        raise AppFolioMigrationError("At least one AppFolio property record is required.")

    fingerprint = _fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        include_hidden=include_hidden,
        records=records,
        source_context_fingerprint=source_context_fingerprint,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint

    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    importable = 0
    skipped_hidden = 0
    invalid = 0
    warning_count = 0

    for record in records:
        source_id = _clean_text(_value(record, "Id", "PropertyId"))
        row_warnings: list[str] = []

        if source_id is None:
            rows.append(
                {
                    "source_id": None,
                    "importable": False,
                    "reason": "AppFolio property Id is required.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if source_id in seen_source_ids:
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": "Duplicate AppFolio property Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        seen_source_ids.add(source_id)

        if _is_hidden(_value(record, "HiddenAt")) and not include_hidden:
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": "Hidden AppFolio property excluded by dry-run settings.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            skipped_hidden += 1
            continue

        name, name_error = _required(
            record, field="Name", aliases=("Name",), max_length=255
        )
        address1, address1_error = _required(
            record, field="Address1", aliases=("Address1", "Address 1"), max_length=255
        )
        city, city_error = _required(
            record, field="City", aliases=("City",), max_length=100
        )
        state, state_error = _required(
            record, field="State", aliases=("State",), max_length=50
        )
        zip_code, zip_error = _required(
            record, field="Zip", aliases=("Zip", "ZipCode", "PostalCode"), max_length=20
        )
        address2, address2_error = _optional(
            record, aliases=("Address2", "Address 2"), max_length=255
        )

        errors = [
            error
            for error in (
                name_error,
                address1_error,
                city_error,
                state_error,
                zip_error,
                address2_error,
            )
            if error is not None
        ]
        if errors:
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": " ".join(errors),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        property_type, type_warnings = _property_type(_value(record, "PropertyType"))
        row_warnings.extend(type_warnings)

        existing = (
            db.query(Property)
            .filter(
                Property.organization_id == run.organization_id,
                Property.name == name,
                Property.address_line1 == address1,
                Property.city == city,
                Property.state == state,
                Property.zip_code == zip_code,
            )
            .first()
        )
        if existing is not None:
            row_warnings.append(
                f"Possible existing target property match: local property #{existing.id}; "
                "a later commit step must resolve rather than duplicate it."
            )

        mapped = {
            "name": name,
            "property_type": property_type,
            "address_line1": address1,
            "address_line2": address2,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "country": "USA",
        }
        rows.append(
            {
                "source_id": source_id,
                "importable": True,
                "reason": None,
                "mapped": mapped,
                "warnings": row_warnings,
            }
        )
        importable += 1
        warning_count += len(row_warnings)

    summary = {
        "resource": "PROPERTIES",
        "source_context_fingerprint": source_context_fingerprint,
        "total": len(records),
        "importable": importable,
        "skipped_hidden": skipped_hidden,
        "invalid": invalid,
        "warning_count": warning_count,
    }

    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return PropertyDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        importable=importable,
        skipped_hidden=skipped_hidden,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )



@dataclass(frozen=True)
class PropertyCommitResult:
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int
    skipped_hidden: int
    warning_count: int
    rows: list[dict[str, Any]]


def commit_properties(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_hidden: bool,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    source_context_fingerprint: str | None = None,
    resolved_existing_matches: dict[str, int] | None = None,
    force_create_new_source_ids: set[str] | None = None,
) -> PropertyCommitResult:
    """Atomically apply the exact reviewed property dry run.

    Existing durable mappings replay safely. Explicit staged MATCH_EXISTING
    decisions create migration metadata only; CREATE_NEW decisions may override
    only the exact possible-match warning for their reviewed source row.
    """
    resolved_existing_matches = {
        str(source_id): int(target_id)
        for source_id, target_id in (resolved_existing_matches or {}).items()
    }
    force_create_new_source_ids = {
        str(source_id) for source_id in (force_create_new_source_ids or set())
    }
    fingerprint = _fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        include_hidden=include_hidden,
        records=records,
        source_context_fingerprint=source_context_fingerprint,
    )
    if expected_fingerprint != fingerprint:
        raise AppFolioMigrationError(
            "Commit payload does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise AppFolioMigrationError(
            "Commit requires the exact latest successful property dry run."
        )

    preview = dry_run_properties(
        db,
        run=run,
        include_hidden=include_hidden,
        records=records,
        source_context_fingerprint=source_context_fingerprint,
    )
    if preview.invalid:
        raise AppFolioMigrationError(
            "Property commit is blocked while the dry run contains invalid records."
        )

    importable_rows = [row for row in preview.rows if row["importable"]]
    source_ids = [str(row["source_id"]) for row in importable_rows]
    source_id_set = set(source_ids)
    resolution_ids = set(resolved_existing_matches) | force_create_new_source_ids
    if resolution_ids - source_id_set:
        raise AppFolioMigrationError(
            "Property resolution state does not match the reviewed dry-run rows."
        )
    if set(resolved_existing_matches) & force_create_new_source_ids:
        raise AppFolioMigrationError(
            "A property source row cannot both match existing and create new."
        )

    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "APPFOLIO",
            PlatformMigrationItem.resource == "PROPERTIES",
            PlatformMigrationItem.source_id.in_(source_ids),
        )
        .order_by(PlatformMigrationItem.id.asc())
        .all()
        if source_ids
        else []
    )
    by_source = {item.source_id: item for item in mappings}

    result_rows: list[dict[str, Any]] = []
    committed = 0
    matched_existing = 0
    changed = False

    for preview_row in importable_rows:
        source_id = str(preview_row["source_id"])
        prior = by_source.get(source_id)
        if prior is not None:
            if prior.target_entity != "PROPERTY":
                raise AppFolioMigrationError(
                    "Property commit mapping is inconsistent and requires manual review."
                )
            target = (
                db.query(Property)
                .filter(
                    Property.id == prior.target_id,
                    Property.organization_id == run.organization_id,
                )
                .first()
            )
            if target is None:
                raise AppFolioMigrationError(
                    "A previously committed target property is missing; manual review required."
                )
            result_rows.append(
                {
                    "source_id": source_id,
                    "target_property_id": target.id,
                    "replayed": True,
                }
            )
            continue

        resolved_target_id = resolved_existing_matches.get(source_id)
        if resolved_target_id is not None:
            target = (
                db.query(Property)
                .filter(
                    Property.id == resolved_target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise AppFolioMigrationError(
                    "Resolved existing property target is no longer available."
                )
            db.add(
                PlatformMigrationItem(
                    run_id=run.id,
                    organization_id=run.organization_id,
                    provider="APPFOLIO",
                    resource="PROPERTIES",
                    source_id=source_id,
                    target_entity="PROPERTY",
                    target_id=target.id,
                    source_fingerprint=fingerprint,
                    created_by_platform_user_id=platform_user_id,
                )
            )
            result_rows.append(
                {
                    "source_id": source_id,
                    "target_property_id": target.id,
                    "replayed": False,
                }
            )
            matched_existing += 1
            changed = True
            continue

        has_possible_match = any(
            warning.startswith("Possible existing target property match:")
            for warning in preview_row["warnings"]
        )
        if has_possible_match and source_id not in force_create_new_source_ids:
            raise AppFolioMigrationError(
                "Property commit is blocked by possible existing target matches; "
                "resolve those conflicts before committing."
            )

        target = Property(
            organization_id=run.organization_id,
            **preview_row["mapped"],
        )
        db.add(target)
        db.flush()
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="APPFOLIO",
                resource="PROPERTIES",
                source_id=source_id,
                target_entity="PROPERTY",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        result_rows.append(
            {
                "source_id": source_id,
                "target_property_id": target.id,
                "replayed": False,
            }
        )
        committed += 1
        changed = True

    if changed:
        run.status = "PROPERTIES_COMMITTED"
        db.flush()

    return PropertyCommitResult(
        fingerprint=fingerprint,
        replayed=not changed,
        committed=committed,
        matched_existing=matched_existing,
        skipped_hidden=preview.skipped_hidden,
        warning_count=preview.warning_count,
        rows=result_rows,
    )


# ---------------------------------------------------------------------------
# Unit Directory staged dry run / controlled commit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnitDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _unit_fingerprint(
    *,
    organization_id: int,
    source_account_ref: str,
    records: list[dict[str, Any]],
    source_context_fingerprint: str | None,
) -> str:
    canonical = json.dumps(
        {
            "provider": "APPFOLIO",
            "resource": "UNITS",
            "organization_id": organization_id,
            "source_account_ref": source_account_ref,
            "source_context_fingerprint": source_context_fingerprint,
            "records": records,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dry_run_units(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    source_context_fingerprint: str | None,
    resolved_existing_matches: dict[str, int] | None = None,
    force_create_new_source_ids: set[str] | None = None,
) -> UnitDryRunResult:
    if run.provider != "APPFOLIO":
        raise AppFolioMigrationError("Migration run is not an AppFolio run.")
    if not records:
        raise AppFolioMigrationError("At least one staged AppFolio Unit record is required.")

    fingerprint = _unit_fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        records=records,
        source_context_fingerprint=source_context_fingerprint,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint

    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    importable = 0
    invalid = 0
    warning_count = 0

    for record in records:
        source_id = _clean_text(_value(record, "Id", "UnitId", "Unit ID"))
        property_source_id = _clean_text(
            _value(record, "PropertyId", "Property ID")
        )
        unit_number = _clean_text(_value(record, "UnitName", "Unit Name", "Unit"))
        row_warnings: list[str] = []

        reasons: list[str] = []
        if source_id is None:
            reasons.append("AppFolio Unit ID is required for controlled commit.")
        elif source_id in seen_source_ids:
            reasons.append("Duplicate AppFolio Unit ID in this dry run.")
        else:
            seen_source_ids.add(source_id)
        if property_source_id is None:
            reasons.append("AppFolio Property ID is required for Unit linkage.")
        if unit_number is None:
            reasons.append("Unit Name is required.")
        elif len(unit_number) > 50:
            reasons.append("Unit Name exceeds the 50-character target unit-number limit.")

        property_mapping = None
        target_property = None
        if property_source_id is not None:
            property_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "PROPERTIES",
                    PlatformMigrationItem.source_id == property_source_id,
                )
                .first()
            )
            if property_mapping is None:
                reasons.append(
                    "Referenced AppFolio Property ID has no durable Property mapping."
                )
            elif property_mapping.target_entity != "PROPERTY":
                reasons.append("Referenced Property mapping is inconsistent.")
            else:
                target_property = (
                    db.query(Property)
                    .filter(
                        Property.id == property_mapping.target_id,
                        Property.organization_id == run.organization_id,
                        Property.is_active.is_(True),
                        Property.deleted_at.is_(None),
                    )
                    .first()
                )
                if target_property is None:
                    reasons.append(
                        "Referenced Property mapping target is not an active same-organization Property."
                    )

        if reasons:
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": " ".join(reasons),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "UNITS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "UNIT":
                rows.append(
                    {
                        "source_id": source_id,
                        "importable": False,
                        "reason": "Existing Unit source mapping is inconsistent.",
                        "mapped": None,
                        "warnings": [],
                    }
                )
                invalid += 1
                continue
            prior_target = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == prior.target_id,
                    Property.organization_id == run.organization_id,
                )
                .first()
            )
            if prior_target is None or prior_target.property_id != target_property.id:
                rows.append(
                    {
                        "source_id": source_id,
                        "importable": False,
                        "reason": "Previously mapped Unit target is missing or belongs to a different mapped Property.",
                        "mapped": None,
                        "warnings": [],
                    }
                )
                invalid += 1
                continue
            row_warnings.append(
                f"Source Unit ID is already mapped to local unit #{prior_target.id}; commit replay will not create a duplicate."
            )
        elif source_id in resolved_existing_matches:
            resolved_target = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == resolved_existing_matches[source_id],
                    Unit.property_id == target_property.id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                    Property.organization_id == run.organization_id,
                )
                .first()
            )
            if resolved_target is None:
                rows.append(
                    {
                        "source_id": source_id,
                        "importable": False,
                        "reason": "Resolved existing Unit target is missing or no longer belongs to the mapped Property.",
                        "mapped": None,
                        "warnings": [],
                    }
                )
                invalid += 1
                continue
            row_warnings.append(
                f"Explicitly matched existing target unit #{resolved_target.id}; commit will create the durable source mapping without overwriting the Unit."
            )
        else:
            existing = (
                db.query(Unit)
                .filter(
                    Unit.property_id == target_property.id,
                    Unit.unit_number == unit_number,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                )
                .first()
            )
            if existing is not None and source_id not in force_create_new_source_ids:
                row_warnings.append(
                    f"Possible existing target unit match: local unit #{existing.id}; explicit match resolution is required before commit."
                )
            elif existing is not None:
                row_warnings.append(
                    f"Explicit CREATE_NEW resolution will create a new Unit despite reviewed same-property match #{existing.id}; the existing Unit will not be changed."
                )

        # The verified basic Unit Directory source contract does not require
        # layout/rent fields. Existing Unit defaults may therefore apply, but
        # they are disclosed as target defaults rather than AppFolio facts.
        row_warnings.append(
            "Bedrooms, bathrooms and monthly rent are not sourced by this basic Unit Directory contract; target Unit defaults apply unless a later verified source supplies them."
        )
        mapped = {
            "property_id": target_property.id,
            "unit_number": unit_number,
            "source_property_id": property_source_id,
        }
        rows.append(
            {
                "source_id": source_id,
                "importable": True,
                "reason": None,
                "mapped": mapped,
                "warnings": row_warnings,
            }
        )
        importable += 1
        warning_count += len(row_warnings)

    summary = {
        "resource": "UNITS",
        "source_context_fingerprint": source_context_fingerprint,
        "total": len(records),
        "importable": importable,
        "invalid": invalid,
        "warning_count": warning_count,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return UnitDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        importable=importable,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


@dataclass(frozen=True)
class UnitCommitResult:
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int
    warning_count: int
    rows: list[dict[str, Any]]


def commit_units(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    source_context_fingerprint: str | None,
    resolved_existing_matches: dict[str, int] | None = None,
    force_create_new_source_ids: set[str] | None = None,
) -> UnitCommitResult:
    fingerprint = _unit_fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        records=records,
        source_context_fingerprint=source_context_fingerprint,
    )
    if expected_fingerprint != fingerprint:
        raise AppFolioMigrationError(
            "Commit payload does not match the supplied Unit dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise AppFolioMigrationError(
            "Commit requires the exact latest successful Unit dry run."
        )

    resolved_existing_matches = dict(resolved_existing_matches or {})
    force_create_new_source_ids = set(force_create_new_source_ids or set())
    preview = dry_run_units(
        db,
        run=run,
        records=records,
        source_context_fingerprint=source_context_fingerprint,
        resolved_existing_matches=resolved_existing_matches,
        force_create_new_source_ids=force_create_new_source_ids,
    )
    if preview.invalid:
        raise AppFolioMigrationError(
            "Unit commit is blocked while the dry run contains invalid records."
        )

    importable_rows = [row for row in preview.rows if row["importable"]]
    source_ids = [str(row["source_id"]) for row in importable_rows]
    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "APPFOLIO",
            PlatformMigrationItem.resource == "UNITS",
            PlatformMigrationItem.source_id.in_(source_ids),
        )
        .all()
        if source_ids
        else []
    )
    by_source = {item.source_id: item for item in mappings}

    new_rows = []
    for row in importable_rows:
        source_id = str(row["source_id"])
        if source_id in by_source:
            continue
        if source_id in resolved_existing_matches:
            continue
        if any(
            warning.startswith("Possible existing target unit match:")
            for warning in row["warnings"]
        ) and source_id not in force_create_new_source_ids:
            raise AppFolioMigrationError(
                "Unit commit is blocked by possible existing target matches; "
                "explicit Unit match/create/skip resolution is required before committing those rows."
            )
        new_rows.append(row)

    if new_rows:
        try:
            require_unit_capacity(
                db,
                organization_id=run.organization_id,
                additional_units=len(new_rows),
            )
        except PlanUnitLimitExceeded as exc:
            raise AppFolioMigrationError(f"PLAN_UNIT_LIMIT_REACHED: {exc}") from exc

    result_rows: list[dict[str, Any]] = []
    committed = 0
    matched_existing = 0
    changed = False

    for row in importable_rows:
        source_id = str(row["source_id"])
        mapped = dict(row["mapped"] or {})
        prior = by_source.get(source_id)
        if prior is not None:
            if prior.target_entity != "UNIT":
                raise AppFolioMigrationError(
                    "Unit commit mapping is inconsistent and requires manual review."
                )
            target = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == prior.target_id,
                    Property.organization_id == run.organization_id,
                )
                .first()
            )
            if (
                target is None
                or target.property_id != int(mapped["property_id"])
            ):
                raise AppFolioMigrationError(
                    "A previously committed target Unit is missing or relationship-inconsistent; manual review required."
                )
            result_rows.append(
                {
                    "source_id": source_id,
                    "target_unit_id": target.id,
                    "replayed": True,
                }
            )
            continue

        resolved_target_id = resolved_existing_matches.get(source_id)
        if resolved_target_id is not None:
            target = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == resolved_target_id,
                    Unit.property_id == int(mapped["property_id"]),
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                    Property.organization_id == run.organization_id,
                )
                .first()
            )
            if target is None:
                raise AppFolioMigrationError(
                    "Resolved existing Unit target is missing or relationship-inconsistent; manual review required."
                )
            db.add(
                PlatformMigrationItem(
                    run_id=run.id,
                    organization_id=run.organization_id,
                    provider="APPFOLIO",
                    resource="UNITS",
                    source_id=source_id,
                    target_entity="UNIT",
                    target_id=target.id,
                    source_fingerprint=fingerprint,
                    created_by_platform_user_id=platform_user_id,
                )
            )
            result_rows.append(
                {
                    "source_id": source_id,
                    "target_unit_id": target.id,
                    "replayed": False,
                }
            )
            matched_existing += 1
            changed = True
            continue

        target = Unit(
            property_id=int(mapped["property_id"]),
            unit_number=str(mapped["unit_number"]),
        )
        db.add(target)
        db.flush()
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="APPFOLIO",
                resource="UNITS",
                source_id=source_id,
                target_entity="UNIT",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        result_rows.append(
            {
                "source_id": source_id,
                "target_unit_id": target.id,
                "replayed": False,
            }
        )
        committed += 1
        changed = True

    if changed:
        run.status = "UNITS_COMMITTED"
        db.flush()

    return UnitCommitResult(
        fingerprint=fingerprint,
        replayed=not changed,
        committed=committed,
        matched_existing=matched_existing,
        warning_count=preview.warning_count,
        rows=result_rows,
    )
