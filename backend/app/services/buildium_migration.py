"""Buildium rental-property migration mapping for Phase 4.14.

This module consumes already-retrieved Buildium v1 rental-property records.
It does not make network calls, persist Buildium credentials, or store raw
provider payloads. Durable source-to-target identity reuses the existing
PlatformMigrationRun / PlatformMigrationItem architecture.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, PropertyType


class BuildiumMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class PropertyDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    skipped_inactive: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class PropertyCommitResult:
    fingerprint: str
    replayed: bool
    committed: int
    skipped_inactive: int
    warning_count: int
    rows: list[dict[str, Any]]


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


def _required_text(
    value: Any,
    *,
    field: str,
    max_length: int,
) -> tuple[str | None, str | None]:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None, f"{field} is required."
    if len(cleaned) > max_length:
        return None, f"{field} exceeds {max_length} characters."
    return cleaned, None


def _optional_text(
    value: Any,
    *,
    field: str,
    max_length: int,
) -> tuple[str | None, str | None]:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None, None
    if len(cleaned) > max_length:
        return None, f"{field} exceeds {max_length} characters."
    return cleaned, None


def _active_flag(value: Any) -> tuple[bool | None, str | None]:
    if isinstance(value, bool):
        return value, None
    return None, "IsActive must be a boolean from the Buildium property resource."


def _year_built(value: Any) -> tuple[int | None, str | None]:
    if value in (None, "", 0, "0"):
        return None, None
    if isinstance(value, bool):
        return None, "YearBuilt must be a four-digit year when supplied."
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None, "YearBuilt must be a four-digit year when supplied."
    current_year = datetime.utcnow().year
    if year < 1000 or year > current_year:
        return None, f"YearBuilt must be between 1000 and {current_year}."
    return year, None


def _property_type(value: Any) -> tuple[str, list[str]]:
    subtype = _clean_text(value)
    if subtype == "SingleFamily":
        return PropertyType.SINGLE_FAMILY.value, []
    if subtype == "MultiFamily":
        return PropertyType.MULTI_FAMILY.value, []
    if subtype in {
        "Industrial",
        "Office",
        "Retail",
        "ShoppingCenter",
        "Storage",
        "ParkingSpace",
    }:
        return PropertyType.COMMERCIAL.value, []
    if subtype == "CondoTownhome":
        return PropertyType.OTHER.value, [
            "Buildium RentalSubType CondoTownhome combines two target property "
            "types; target preview uses OTHER rather than guessing condo vs townhouse."
        ]
    if subtype is None:
        return PropertyType.OTHER.value, [
            "Buildium RentalSubType is not recorded; target preview uses OTHER."
        ]
    return PropertyType.OTHER.value, [
        f"Unrecognized Buildium RentalSubType {subtype!r}; target preview uses OTHER."
    ]


def _fingerprint(
    *,
    organization_id: int,
    source_account_ref: str,
    include_inactive: bool,
    records: list[dict[str, Any]],
) -> str:
    canonical = json.dumps(
        {
            "provider": "BUILDIUM",
            "resource": "PROPERTIES",
            "organization_id": organization_id,
            "source_account_ref": source_account_ref,
            "include_inactive": include_inactive,
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
    include_inactive: bool,
    records: list[dict[str, Any]],
) -> PropertyDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumMigrationError("At least one Buildium property record is required.")

    fingerprint = _fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        include_inactive=include_inactive,
        records=records,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint

    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    importable = 0
    skipped_inactive = 0
    invalid = 0
    warning_count = 0

    for record in records:
        source_id = _positive_source_id(record.get("Id"))
        if source_id is None:
            rows.append(
                {
                    "source_id": None,
                    "importable": False,
                    "reason": "Buildium property Id must be a positive integer.",
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
                    "reason": "Duplicate Buildium property Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        seen_source_ids.add(source_id)

        active, active_error = _active_flag(record.get("IsActive"))
        if active_error is not None:
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": active_error,
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if active is False and not include_inactive:
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": "Inactive Buildium property excluded by dry-run settings.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            skipped_inactive += 1
            continue

        address = record.get("Address")
        if not isinstance(address, dict):
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": "Buildium Address object is required.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        name, name_error = _required_text(record.get("Name"), field="Name", max_length=255)
        address1, address1_error = _required_text(
            address.get("AddressLine1"), field="Address.AddressLine1", max_length=255
        )
        address2, address2_error = _optional_text(
            address.get("AddressLine2"), field="Address.AddressLine2", max_length=255
        )
        address3, address3_error = _optional_text(
            address.get("AddressLine3"), field="Address.AddressLine3", max_length=255
        )
        city, city_error = _required_text(
            address.get("City"), field="Address.City", max_length=100
        )
        state, state_error = _required_text(
            address.get("State"), field="Address.State", max_length=50
        )
        postal, postal_error = _required_text(
            address.get("PostalCode"), field="Address.PostalCode", max_length=20
        )
        country, country_error = _required_text(
            address.get("Country"), field="Address.Country", max_length=100
        )
        year_built, year_error = _year_built(record.get("YearBuilt"))

        errors = [
            error
            for error in (
                name_error,
                address1_error,
                address2_error,
                address3_error,
                city_error,
                state_error,
                postal_error,
                country_error,
                year_error,
            )
            if error is not None
        ]
        if address3 is not None:
            errors.append(
                "Address.AddressLine3 is populated but the target Property contract "
                "has no third address line; controlled commit is blocked to avoid data loss."
            )
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

        property_type, row_warnings = _property_type(record.get("RentalSubType"))
        existing = (
            db.query(Property)
            .filter(
                Property.organization_id == run.organization_id,
                Property.name == name,
                Property.address_line1 == address1,
                Property.city == city,
                Property.state == state,
                Property.zip_code == postal,
            )
            .first()
        )
        if existing is not None:
            row_warnings.append(
                f"Possible existing target property match: local property #{existing.id}; "
                "controlled commit is blocked until the match is explicitly reviewed."
            )

        mapped = {
            "name": name,
            "property_type": property_type,
            "address_line1": address1,
            "address_line2": address2,
            "city": city,
            "state": state,
            "zip_code": postal,
            "country": country,
            "year_built": year_built,
            "is_active": active,
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
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "importable": importable,
        "skipped_inactive": skipped_inactive,
        "invalid": invalid,
        "warning_count": warning_count,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
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
        skipped_inactive=skipped_inactive,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


def commit_properties(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
) -> PropertyCommitResult:
    """Atomically commit the exact latest reviewed Buildium property dry run."""
    fingerprint = _fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        include_inactive=include_inactive,
        records=records,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumMigrationError(
            "Commit payload does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumMigrationError(
            "Commit requires the exact latest successful Buildium property dry run."
        )

    preview = dry_run_properties(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
    )
    if preview.invalid:
        raise BuildiumMigrationError(
            "Property commit is blocked while the dry run contains invalid records."
        )

    importable_rows = [row for row in preview.rows if row["importable"]]
    source_ids = [str(row["source_id"]) for row in importable_rows]
    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
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
    changed = False

    for preview_row in importable_rows:
        source_id = str(preview_row["source_id"])
        prior = by_source.get(source_id)
        if prior is not None:
            if prior.target_entity != "PROPERTY":
                raise BuildiumMigrationError(
                    "Buildium property mapping is inconsistent and requires manual review."
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
                raise BuildiumMigrationError(
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

        if any(
            warning.startswith("Possible existing target property match:")
            for warning in preview_row["warnings"]
        ):
            raise BuildiumMigrationError(
                "Property commit is blocked by possible existing target matches; "
                "a later review batch must explicitly resolve them before commit."
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
                provider="BUILDIUM",
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
        skipped_inactive=preview.skipped_inactive,
        warning_count=preview.warning_count,
        rows=result_rows,
    )
