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
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class PropertyCommitResult:
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int
    skipped_inactive: int
    skipped_review: int
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


def _normalize_resolutions(
    resolutions: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for item in resolutions or []:
        source_id = _positive_source_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumMigrationError(
                "Buildium property review source_id must be a positive integer."
            )
        if source_id in normalized:
            raise BuildiumMigrationError(
                f"Duplicate Buildium property review decision for source ID {source_id}."
            )
        action = _clean_text(item.get("action"))
        if action not in {"MATCH_EXISTING", "CREATE_NEW", "SKIP"}:
            raise BuildiumMigrationError("Unsupported Buildium property review action.")
        target_property_id = item.get("target_property_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_property_id, bool):
                raise BuildiumMigrationError(
                    "MATCH_EXISTING requires a positive target Property ID."
                )
            try:
                target_property_id = int(target_property_id)
            except (TypeError, ValueError):
                raise BuildiumMigrationError(
                    "MATCH_EXISTING requires a positive target Property ID."
                )
            if target_property_id < 1:
                raise BuildiumMigrationError(
                    "MATCH_EXISTING requires a positive target Property ID."
                )
        elif target_property_id is not None:
            raise BuildiumMigrationError(
                "target_property_id is only valid for MATCH_EXISTING."
            )
        normalized[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_property_id": target_property_id,
        }
    return normalized


def _fingerprint(
    *,
    organization_id: int,
    source_account_ref: str,
    include_inactive: bool,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    fingerprint_payload: dict[str, Any] = {
        "provider": "BUILDIUM",
        "resource": "PROPERTIES",
        "organization_id": organization_id,
        "source_account_ref": source_account_ref,
        "include_inactive": include_inactive,
        "records": records,
    }
    # Preserve the verified Phase 4.14 foundation fingerprint for ordinary
    # no-review runs. Review state extends, rather than rewrites, that contract.
    if resolution_map:
        fingerprint_payload["resolutions"] = [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ]
    canonical = json.dumps(
        fingerprint_payload,
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
    resolutions: list[dict[str, Any]] | None = None,
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
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    reviewable_source_ids: set[str] = set()
    importable = 0
    skipped_inactive = 0
    skipped_review = 0
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

        reviewable_source_ids.add(source_id)
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
        durable_mapping = (
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
        resolution = resolution_map.get(source_id)
        resolution_action = resolution["action"] if resolution else None
        resolution_target_id = (
            resolution["target_property_id"] if resolution else None
        )

        if durable_mapping is not None:
            if durable_mapping.target_entity != "PROPERTY":
                raise BuildiumMigrationError(
                    "Buildium property mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                resolution_action != "MATCH_EXISTING"
                or resolution_target_id != durable_mapping.target_id
            ):
                raise BuildiumMigrationError(
                    f"Buildium source Property ID {source_id} already has a durable "
                    "mapping and cannot be re-resolved."
                )
            row_warnings.append(
                f"Buildium source Property ID {source_id} is already durably mapped "
                f"to local property #{durable_mapping.target_id}; commit will replay."
            )

        if existing is not None:
            row_warnings.append(
                f"Possible existing target property match: local property #{existing.id}; "
                "controlled commit requires an explicit MATCH_EXISTING or CREATE_NEW review decision."
            )

        if resolution_action == "CREATE_NEW" and existing is None:
            raise BuildiumMigrationError(
                f"CREATE_NEW review for Buildium source Property ID {source_id} is only "
                "valid when the dry run found a possible existing target match."
            )

        if resolution_action == "MATCH_EXISTING":
            target = (
                db.query(Property)
                .filter(
                    Property.id == resolution_target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise BuildiumMigrationError(
                    f"Reviewed target Property #{resolution_target_id} for Buildium "
                    f"source Property ID {source_id} is not an active same-organization property."
                )
            row_warnings.append(
                f"Reviewed MATCH_EXISTING target: local property #{target.id}; "
                "controlled commit will create source mapping metadata only and will not overwrite it."
            )
        elif resolution_action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "importable": False,
                    "reason": "Explicitly skipped after Buildium property review.",
                    "mapped": None,
                    "warnings": row_warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_property_id": None,
                }
            )
            skipped_review += 1
            warning_count += len(row_warnings)
            continue

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
                "resolution_action": resolution_action,
                "resolution_target_property_id": resolution_target_id,
            }
        )
        importable += 1
        warning_count += len(row_warnings)

    unresolved_resolution_ids = sorted(
        set(resolution_map) - reviewable_source_ids,
        key=int,
    )
    if unresolved_resolution_ids:
        raise BuildiumMigrationError(
            "Buildium property review decisions may reference only source rows "
            "that are otherwise valid and included in the current dry run: "
            + ", ".join(unresolved_resolution_ids)
        )

    summary = {
        "resource": "PROPERTIES",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "importable": importable,
        "skipped_inactive": skipped_inactive,
        "skipped_review": skipped_review,
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
        skipped_review=skipped_review,
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
    resolutions: list[dict[str, Any]] | None = None,
) -> PropertyCommitResult:
    """Atomically commit the exact latest reviewed Buildium property dry run."""
    fingerprint = _fingerprint(
        organization_id=run.organization_id,
        source_account_ref=run.source_account_ref,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
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
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumMigrationError(
            "Property commit is blocked while the dry run contains invalid records."
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

        resolution = resolution_map.get(source_id)
        resolution_action = resolution["action"] if resolution else None
        if resolution_action == "MATCH_EXISTING":
            target_id = resolution["target_property_id"]
            target = (
                db.query(Property)
                .filter(
                    Property.id == target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise BuildiumMigrationError(
                    f"Reviewed existing target Property #{target_id} is no longer "
                    "an active same-organization property."
                )
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
            matched_existing += 1
            changed = True
            continue

        has_possible_match = any(
            warning.startswith("Possible existing target property match:")
            for warning in preview_row["warnings"]
        )
        if has_possible_match and resolution_action != "CREATE_NEW":
            raise BuildiumMigrationError(
                "Property commit is blocked by possible existing target matches; "
                "supply the exact reviewed MATCH_EXISTING or CREATE_NEW decision."
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

    review_recorded = False
    if changed:
        run.status = "PROPERTIES_COMMITTED"
        db.flush()
    elif (
        preview.skipped_review
        and not result_rows
        and run.status == "DRY_RUN_READY"
    ):
        # A skip-only commit is a meaningful reviewed no-op. Record that the
        # exact fingerprint was committed without inventing a fake target item.
        run.status = "PROPERTIES_REVIEWED"
        db.flush()
        review_recorded = True

    return PropertyCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        committed=committed,
        matched_existing=matched_existing,
        skipped_inactive=preview.skipped_inactive,
        skipped_review=preview.skipped_review,
        warning_count=preview.warning_count,
        rows=result_rows,
    )
