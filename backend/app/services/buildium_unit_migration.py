"""Buildium rental-unit migration mapping for Phase 4.14.

This module consumes already-retrieved Buildium v1 rental-unit records and
reuses the existing provider-labelled PlatformMigrationRun /
PlatformMigrationItem architecture. It performs no provider network calls and
stores no Buildium credentials or raw response bodies.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit


class BuildiumUnitMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class UnitDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class UnitCommitResult:
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


_BEDROOMS = {
    "Studio": 0,
    "OneBed": 1,
    "TwoBed": 2,
    "ThreeBed": 3,
    "FourBed": 4,
    "FiveBed": 5,
    "SixBed": 6,
    "SevenBed": 7,
    "EightBed": 8,
}
_BATHROOMS = {
    "OneBath": Decimal("1.0"),
    "OnePointFiveBath": Decimal("1.5"),
    "TwoBath": Decimal("2.0"),
    "TwoPointFiveBath": Decimal("2.5"),
    "ThreeBath": Decimal("3.0"),
    "ThreePointFiveBath": Decimal("3.5"),
    "FourBath": Decimal("4.0"),
    "FourPointFiveBath": Decimal("4.5"),
    "FiveBath": Decimal("5.0"),
}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_source_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return str(number) if number > 0 else None


def _required_text(value: Any, *, field: str, max_length: int) -> tuple[str | None, str | None]:
    text = _clean_text(value)
    if text is None:
        return None, f"{field} is required."
    if len(text) > max_length:
        return None, f"{field} exceeds {max_length} characters."
    return text, None


def _optional_text(value: Any, *, field: str, max_length: int) -> tuple[str | None, str | None]:
    text = _clean_text(value)
    if text is None:
        return None, None
    if len(text) > max_length:
        return None, f"{field} exceeds {max_length} characters."
    return text, None


def _nonnegative_money(value: Any, *, field: str) -> tuple[Decimal | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, f"{field} is required and must be a non-negative amount."
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field} must be a non-negative amount."
    if not amount.is_finite() or amount < 0:
        return None, f"{field} must be a non-negative amount."
    quantized = amount.quantize(Decimal("0.01"))
    if amount != quantized:
        return None, f"{field} cannot have more than two decimal places."
    if quantized > Decimal("99999999.99"):
        return None, f"{field} exceeds the target Unit amount range."
    return quantized, None


def _unit_size(value: Any) -> tuple[int | None, str | None]:
    if value in (None, "", 0, "0"):
        return None, None
    if isinstance(value, bool):
        return None, "UnitSize must be a positive integer when supplied."
    try:
        size = int(value)
    except (TypeError, ValueError):
        return None, "UnitSize must be a positive integer when supplied."
    if size < 1:
        return None, "UnitSize must be a positive integer when supplied."
    return size, None


def _bedrooms(value: Any) -> tuple[int | None, str | None]:
    label = _clean_text(value)
    if label in _BEDROOMS:
        return _BEDROOMS[label], None
    if label == "NineBedPlus":
        return None, (
            "Buildium UnitBedrooms NineBedPlus cannot be represented exactly by the "
            "target integer bedroom contract."
        )
    if label in (None, "NotSet"):
        return None, (
            "Buildium UnitBedrooms is not set; controlled create is blocked rather "
            "than treating unknown bedroom count as a studio."
        )
    return None, f"Unsupported Buildium UnitBedrooms value {label!r}."


def _bathrooms(value: Any) -> tuple[Decimal | None, str | None]:
    label = _clean_text(value)
    if label in _BATHROOMS:
        return _BATHROOMS[label], None
    if label == "FivePlusBath":
        return None, (
            "Buildium UnitBathrooms FivePlusBath cannot be represented exactly by "
            "the target numeric bathroom contract."
        )
    if label in (None, "NotSet"):
        return None, (
            "Buildium UnitBathrooms is not set; controlled create is blocked rather "
            "than inventing a bathroom count."
        )
    return None, f"Unsupported Buildium UnitBathrooms value {label!r}."


def _boolean(value: Any, *, field: str, required: bool) -> tuple[bool | None, str | None]:
    if isinstance(value, bool):
        return value, None
    if value is None and not required:
        return None, None
    return None, f"{field} must be a boolean when supplied by Buildium."


def _normalize_resolutions(
    resolutions: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for item in resolutions or []:
        source_id = _positive_source_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumUnitMigrationError(
                "Buildium Unit review source_id must be a positive integer."
            )
        if source_id in normalized:
            raise BuildiumUnitMigrationError(
                f"Duplicate Buildium Unit review decision for source ID {source_id}."
            )
        action = _clean_text(item.get("action"))
        if action not in {"MATCH_EXISTING", "CREATE_NEW", "SKIP"}:
            raise BuildiumUnitMigrationError("Unsupported Buildium Unit review action.")
        target_unit_id = item.get("target_unit_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_unit_id, bool):
                raise BuildiumUnitMigrationError(
                    "MATCH_EXISTING requires a positive target Unit ID."
                )
            try:
                target_unit_id = int(target_unit_id)
            except (TypeError, ValueError):
                raise BuildiumUnitMigrationError(
                    "MATCH_EXISTING requires a positive target Unit ID."
                )
            if target_unit_id < 1:
                raise BuildiumUnitMigrationError(
                    "MATCH_EXISTING requires a positive target Unit ID."
                )
        elif target_unit_id is not None:
            raise BuildiumUnitMigrationError(
                "target_unit_id is only valid for MATCH_EXISTING."
            )
        normalized[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_unit_id": target_unit_id,
        }
    return normalized


def _property_mapping_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_ids = sorted(
        {
            source_id
            for source_id in (
                _positive_source_id(record.get("PropertyId"))
                for record in records
            )
            if source_id is not None
        },
        key=int,
    )
    state: list[dict[str, Any]] = []
    for source_id in source_ids:
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        target = None
        if mapping is not None and mapping.target_entity == "PROPERTY":
            target = (
                db.query(Property)
                .filter(
                    Property.id == mapping.target_id,
                    Property.organization_id == run.organization_id,
                )
                .first()
            )
        state.append(
            {
                "source_property_id": source_id,
                "mapping_target_entity": mapping.target_entity if mapping else None,
                "mapping_target_id": mapping.target_id if mapping else None,
                "mapping_source_fingerprint": mapping.source_fingerprint if mapping else None,
                "target_active": bool(
                    target is not None
                    and target.is_active
                    and target.deleted_at is None
                ),
            }
        )
    return state


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "UNITS",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "property_mappings": _property_mapping_state(db, run=run, records=records),
        "resolutions": [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _mapped_property(
    db: Session,
    *,
    run: PlatformMigrationRun,
    source_property_id: str,
) -> tuple[PlatformMigrationItem | None, Property | None]:
    mapping = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == "PROPERTIES",
            PlatformMigrationItem.source_id == source_property_id,
        )
        .first()
    )
    if mapping is None or mapping.target_entity != "PROPERTY":
        return mapping, None
    target = (
        db.query(Property)
        .filter(
            Property.id == mapping.target_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
        .first()
    )
    return mapping, target


def _address_matches_property(
    address: dict[str, Any],
    property_row: Property,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    values: dict[str, str | None] = {}
    specs = (
        ("address_line1", "AddressLine1", 255, True),
        ("address_line2", "AddressLine2", 255, False),
        ("city", "City", 100, True),
        ("state", "State", 50, True),
        ("zip_code", "PostalCode", 20, True),
        ("country", "Country", 100, True),
    )
    for target_field, source_field, max_length, required in specs:
        if required:
            value, error = _required_text(
                address.get(source_field),
                field=f"Address.{source_field}",
                max_length=max_length,
            )
        else:
            value, error = _optional_text(
                address.get(source_field),
                field=f"Address.{source_field}",
                max_length=max_length,
            )
        values[target_field] = value
        if error:
            errors.append(error)

    address3, address3_error = _optional_text(
        address.get("AddressLine3"),
        field="Address.AddressLine3",
        max_length=255,
    )
    if address3_error:
        errors.append(address3_error)
    if address3 is not None:
        errors.append(
            "Address.AddressLine3 is populated but the target Unit has no address "
            "fields; controlled commit is blocked to avoid data loss."
        )
    if errors:
        return False, errors

    for field, source_value in values.items():
        target_value = getattr(property_row, field)
        left = _clean_text(source_value)
        right = _clean_text(target_value)
        if (left or "").casefold() != (right or "").casefold():
            errors.append(
                "Buildium Unit address differs from the mapped target Property address; "
                "the current target Unit model has no independent address fields."
            )
            break
    return not errors, errors


def dry_run_units(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> UnitDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumUnitMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumUnitMigrationError("At least one Buildium Unit record is required.")

    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    reviewable_source_ids: set[str] = set()
    importable = 0
    skipped_review = 0
    invalid = 0
    warning_count = 0

    for record in records:
        source_id = _positive_source_id(record.get("Id"))
        if source_id is None:
            rows.append({
                "source_id": None,
                "source_property_id": None,
                "importable": False,
                "reason": "Buildium Unit Id must be a positive integer.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        if source_id in seen_source_ids:
            rows.append({
                "source_id": source_id,
                "source_property_id": _positive_source_id(record.get("PropertyId")),
                "importable": False,
                "reason": "Duplicate Buildium Unit Id in this dry run.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        seen_source_ids.add(source_id)

        source_property_id = _positive_source_id(record.get("PropertyId"))
        if source_property_id is None:
            rows.append({
                "source_id": source_id,
                "source_property_id": None,
                "importable": False,
                "reason": "Buildium Unit PropertyId must be a positive integer.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue

        property_mapping, target_property = _mapped_property(
            db,
            run=run,
            source_property_id=source_property_id,
        )
        if property_mapping is None:
            rows.append({
                "source_id": source_id,
                "source_property_id": source_property_id,
                "importable": False,
                "reason": (
                    f"Buildium source Property ID {source_property_id} has no durable "
                    "Property mapping in this migration run."
                ),
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        if property_mapping.target_entity != "PROPERTY" or target_property is None:
            rows.append({
                "source_id": source_id,
                "source_property_id": source_property_id,
                "importable": False,
                "reason": (
                    f"Buildium source Property ID {source_property_id} no longer maps "
                    "to an active same-organization Property."
                ),
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue

        unit_number, unit_number_error = _required_text(
            record.get("UnitNumber"),
            field="UnitNumber",
            max_length=30,
        )
        description = _clean_text(record.get("Description"))
        rent, rent_error = _nonnegative_money(record.get("MarketRent"), field="MarketRent")
        size, size_error = _unit_size(record.get("UnitSize"))
        bedrooms, bedroom_error = _bedrooms(record.get("UnitBedrooms"))
        bathrooms, bathroom_error = _bathrooms(record.get("UnitBathrooms"))
        listed, listed_error = _boolean(record.get("IsUnitListed"), field="IsUnitListed", required=True)
        occupied, occupied_error = _boolean(
            record.get("IsUnitOccupied"),
            field="IsUnitOccupied",
            required=False,
        )

        errors = [
            error
            for error in (
                unit_number_error,
                rent_error,
                size_error,
                bedroom_error,
                bathroom_error,
                listed_error,
                occupied_error,
            )
            if error is not None
        ]
        if description is not None:
            errors.append(
                "Buildium Unit Description is populated but the target Unit has no "
                "description field; controlled commit is blocked to avoid data loss."
            )
        address = record.get("Address")
        if not isinstance(address, dict):
            errors.append("Buildium Unit Address object is required.")
        else:
            _, address_errors = _address_matches_property(address, target_property)
            errors.extend(address_errors)

        if errors:
            rows.append({
                "source_id": source_id,
                "source_property_id": source_property_id,
                "importable": False,
                "reason": " ".join(errors),
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue

        reviewable_source_ids.add(source_id)
        warnings: list[str] = []
        if occupied is not None:
            warnings.append(
                "Buildium IsUnitOccupied is source evidence only; this migration does "
                "not infer Unit availability, Tenant identity, occupancy or Lease state."
            )

        durable_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "UNITS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        existing = (
            db.query(Unit)
            .filter(
                Unit.property_id == target_property.id,
                func.lower(Unit.unit_number) == unit_number.lower(),
                Unit.is_active.is_(True),
                Unit.deleted_at.is_(None),
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        resolution_action = resolution["action"] if resolution else None
        resolution_target_id = resolution["target_unit_id"] if resolution else None

        if durable_mapping is not None:
            if durable_mapping.target_entity != "UNIT":
                raise BuildiumUnitMigrationError(
                    "Buildium Unit mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                resolution_action != "MATCH_EXISTING"
                or resolution_target_id != durable_mapping.target_id
            ):
                raise BuildiumUnitMigrationError(
                    f"Buildium source Unit ID {source_id} already has a durable "
                    "mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source Unit ID {source_id} is already durably mapped "
                f"to local Unit #{durable_mapping.target_id}; commit will replay."
            )

        if existing is not None:
            warnings.append(
                f"Possible existing target Unit match: local Unit #{existing.id}; "
                "controlled commit requires explicit MATCH_EXISTING or CREATE_NEW review."
            )

        if resolution_action == "CREATE_NEW" and existing is None:
            raise BuildiumUnitMigrationError(
                f"CREATE_NEW review for Buildium source Unit ID {source_id} is only "
                "valid when the dry run found a possible existing target Unit match."
            )
        if resolution_action == "MATCH_EXISTING":
            target_unit = (
                db.query(Unit)
                .filter(
                    Unit.id == resolution_target_id,
                    Unit.property_id == target_property.id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                )
                .first()
            )
            if target_unit is None:
                raise BuildiumUnitMigrationError(
                    f"Reviewed target Unit #{resolution_target_id} for Buildium source "
                    f"Unit ID {source_id} is not active under the mapped Property."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Unit #{target_unit.id}; "
                "controlled commit will create source mapping metadata only."
            )
        elif resolution_action == "SKIP":
            rows.append({
                "source_id": source_id,
                "source_property_id": source_property_id,
                "importable": False,
                "reason": "Explicitly skipped after Buildium Unit review.",
                "mapped": None,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_unit_id": None,
            })
            skipped_review += 1
            warning_count += len(warnings)
            continue

        mapped = {
            "target_property_id": target_property.id,
            "unit_number": unit_number,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "square_feet": size,
            "monthly_rent": rent,
            "is_available": None,
            "is_listed": listed,
            "is_active": True,
        }
        rows.append({
            "source_id": source_id,
            "source_property_id": source_property_id,
            "importable": True,
            "reason": None,
            "mapped": mapped,
            "warnings": warnings,
            "resolution_action": resolution_action,
            "resolution_target_unit_id": resolution_target_id,
        })
        importable += 1
        warning_count += len(warnings)

    unresolved = sorted(set(resolution_map) - reviewable_source_ids, key=int)
    if unresolved:
        raise BuildiumUnitMigrationError(
            "Buildium Unit review decisions may reference only source rows that are "
            "otherwise valid and linked to a current durable Property mapping: "
            + ", ".join(unresolved)
        )

    summary = {
        "resource": "UNITS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "importable": importable,
        "skipped_review": skipped_review,
        "invalid": invalid,
        "warning_count": warning_count,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
        "occupancy_inferred": False,
        "lease_mutation": False,
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
        skipped_review=skipped_review,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


def commit_units(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> UnitCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumUnitMigrationError(
            "Commit payload or durable Property mapping state does not match the "
            "supplied Buildium Unit dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumUnitMigrationError(
            "Commit requires the exact latest successful Buildium Unit dry run."
        )

    preview = dry_run_units(db, run=run, records=records, resolutions=resolutions)
    if preview.invalid:
        raise BuildiumUnitMigrationError(
            "Buildium Unit commit is blocked while the dry run contains invalid records."
        )

    resolution_map = _normalize_resolutions(resolutions)
    importable_rows = [row for row in preview.rows if row["importable"]]
    source_ids = [str(row["source_id"]) for row in importable_rows]
    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == "UNITS",
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
        target_property_id = int(preview_row["mapped"]["target_property_id"])
        prior = by_source.get(source_id)
        if prior is not None:
            if prior.target_entity != "UNIT":
                raise BuildiumUnitMigrationError(
                    "Buildium Unit mapping is inconsistent and requires manual review."
                )
            target = (
                db.query(Unit)
                .filter(
                    Unit.id == prior.target_id,
                    Unit.property_id == target_property_id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise BuildiumUnitMigrationError(
                    "A previously committed target Unit is missing or no longer belongs "
                    "to the mapped Property; manual review required."
                )
            result_rows.append({
                "source_id": source_id,
                "target_unit_id": target.id,
                "replayed": True,
            })
            continue

        resolution = resolution_map.get(source_id)
        resolution_action = resolution["action"] if resolution else None
        if resolution_action == "MATCH_EXISTING":
            target_unit_id = resolution["target_unit_id"]
            target = (
                db.query(Unit)
                .filter(
                    Unit.id == target_unit_id,
                    Unit.property_id == target_property_id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise BuildiumUnitMigrationError(
                    f"Reviewed target Unit #{target_unit_id} is no longer active under "
                    "the mapped Property."
                )
            db.add(PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="UNITS",
                source_id=source_id,
                target_entity="UNIT",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            ))
            result_rows.append({
                "source_id": source_id,
                "target_unit_id": target.id,
                "replayed": False,
            })
            matched_existing += 1
            changed = True
            continue

        has_possible_match = any(
            warning.startswith("Possible existing target Unit match:")
            for warning in preview_row["warnings"]
        )
        if has_possible_match and resolution_action != "CREATE_NEW":
            raise BuildiumUnitMigrationError(
                "Buildium Unit commit is blocked by possible existing target matches; "
                "supply the exact reviewed MATCH_EXISTING or CREATE_NEW decision."
            )

        mapped = dict(preview_row["mapped"])
        mapped.pop("target_property_id")
        target = Unit(property_id=target_property_id, **mapped)
        db.add(target)
        db.flush()
        # Unit.is_available has a legacy Python default of True. Buildium's
        # IsUnitOccupied is not equivalent to our availability field, so restore
        # the deliberately unknown value after INSERT rather than inventing
        # vacancy/availability from provider occupancy evidence.
        target.is_available = None
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=run.id,
            organization_id=run.organization_id,
            provider="BUILDIUM",
            resource="UNITS",
            source_id=source_id,
            target_entity="UNIT",
            target_id=target.id,
            source_fingerprint=fingerprint,
            created_by_platform_user_id=platform_user_id,
        ))
        result_rows.append({
            "source_id": source_id,
            "target_unit_id": target.id,
            "replayed": False,
        })
        committed += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "UNITS_COMMITTED"
        db.flush()
    elif preview.skipped_review and not result_rows and run.status == "DRY_RUN_READY":
        run.status = "UNITS_REVIEWED"
        db.flush()
        review_recorded = True

    return UnitCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        committed=committed,
        matched_existing=matched_existing,
        skipped_review=preview.skipped_review,
        warning_count=preview.warning_count,
        rows=result_rows,
    )
