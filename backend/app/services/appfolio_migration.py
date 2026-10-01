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
from app.models.property import Property, PropertyType


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
