"""Buildium rental-owner identity mapping for Phase 4.14.

Rental owners are login-bearing OWNER users in the target product. This module
therefore supports reviewed mapping to an existing same-organization OWNER only.
It never creates a User, PropertyOwner percentage/primary relationship, tax
profile, or provider credential.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property
from app.models.user import User, UserRole


class BuildiumOwnerMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class OwnerDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_inactive: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class OwnerCommitResult:
    fingerprint: str
    replayed: bool
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


def _bool(value: Any, *, field: str) -> tuple[bool | None, str | None]:
    if isinstance(value, bool):
        return value, None
    return None, f"{field} must be a boolean from the Buildium rental-owner resource."


def _email(value: Any) -> tuple[str | None, str | None]:
    text = _clean_text(value)
    if text is None:
        return None, "Email is required for safe mapping to an existing OWNER user."
    if len(text) > 255 or not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", text):
        return None, "Email must contain one valid source email address."
    return text.lower(), None


def _display_name(record: dict[str, Any]) -> tuple[str | None, str | None]:
    is_company, error = _bool(record.get("IsCompany"), field="IsCompany")
    if error:
        return None, error
    if is_company:
        company = _clean_text(record.get("CompanyName"))
        if not company:
            return None, "CompanyName is required when Buildium IsCompany is true."
        if len(company) > 127:
            return None, "CompanyName exceeds 127 characters."
        return company, None
    first = _clean_text(record.get("FirstName"))
    last = _clean_text(record.get("LastName"))
    if not first or not last:
        return None, "FirstName and LastName are required when Buildium IsCompany is false."
    if len(first) > 127 or len(last) > 127:
        return None, "FirstName or LastName exceeds 127 characters."
    return f"{first} {last}", None


def _property_ids(value: Any) -> tuple[list[str], str | None]:
    if value is None:
        return [], None
    if not isinstance(value, list):
        return [], "PropertyIds must be an array of positive Buildium Property IDs."
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        source_id = _positive_source_id(raw)
        if source_id is None:
            return [], "PropertyIds must contain only positive Buildium Property IDs."
        if source_id in seen:
            return [], "PropertyIds contains a duplicate Buildium Property ID."
        seen.add(source_id)
        result.append(source_id)
    return result, None


def _normalize_resolutions(
    resolutions: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for item in resolutions or []:
        source_id = _positive_source_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumOwnerMigrationError(
                "Buildium Owner review source_id must be a positive integer."
            )
        if source_id in normalized:
            raise BuildiumOwnerMigrationError(
                f"Duplicate Buildium Owner review decision for source ID {source_id}."
            )
        action = _clean_text(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumOwnerMigrationError(
                "Buildium Owner review supports only MATCH_EXISTING or SKIP; "
                "creating login-bearing OWNER users from provider contact data is not supported."
            )
        target_owner_user_id = item.get("target_owner_user_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_owner_user_id, bool):
                raise BuildiumOwnerMigrationError(
                    "MATCH_EXISTING requires a positive target OWNER user ID."
                )
            try:
                target_owner_user_id = int(target_owner_user_id)
            except (TypeError, ValueError):
                raise BuildiumOwnerMigrationError(
                    "MATCH_EXISTING requires a positive target OWNER user ID."
                )
            if target_owner_user_id < 1:
                raise BuildiumOwnerMigrationError(
                    "MATCH_EXISTING requires a positive target OWNER user ID."
                )
        elif target_owner_user_id is not None:
            raise BuildiumOwnerMigrationError(
                "target_owner_user_id is only valid for MATCH_EXISTING."
            )
        normalized[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_owner_user_id": target_owner_user_id,
        }
    return normalized


def _property_mapping_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    property_sources: set[str] = set()
    for record in records:
        values, error = _property_ids(record.get("PropertyIds"))
        if error is None:
            property_sources.update(values)
    state: list[dict[str, Any]] = []
    for source_id in sorted(property_sources, key=int):
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
        state.append({
            "source_property_id": source_id,
            "mapping_target_entity": mapping.target_entity if mapping else None,
            "mapping_target_id": mapping.target_id if mapping else None,
            "mapping_source_fingerprint": mapping.source_fingerprint if mapping else None,
            "target_active": bool(target is not None and target.is_active and target.deleted_at is None),
        })
    return state


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    canonical = json.dumps(
        {
            "provider": "BUILDIUM",
            "resource": "OWNERS",
            "organization_id": run.organization_id,
            "source_account_ref": run.source_account_ref,
            "include_inactive": include_inactive,
            "records": records,
            "property_mappings": _property_mapping_state(db, run=run, records=records),
            "resolutions": [resolution_map[key] for key in sorted(resolution_map, key=int)],
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _mapped_properties(
    db: Session,
    *,
    run: PlatformMigrationRun,
    source_property_ids: list[str],
) -> tuple[list[int], list[str]]:
    targets: list[int] = []
    errors: list[str] = []
    for source_id in source_property_ids:
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
        if mapping is None or mapping.target_entity != "PROPERTY":
            errors.append(
                f"Buildium source Property ID {source_id} has no durable Property mapping in this migration run."
            )
            continue
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
        if target is None:
            errors.append(
                f"Buildium source Property ID {source_id} no longer maps to an active same-organization Property."
            )
            continue
        targets.append(target.id)
    return targets, errors


def dry_run_owners(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> OwnerDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumOwnerMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumOwnerMigrationError("At least one Buildium rental-owner record is required.")

    fingerprint = _fingerprint(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    reviewable_ids: set[str] = set()
    reviewable = skipped_inactive = skipped_review = invalid = warning_count = 0

    for record in records:
        source_id = _positive_source_id(record.get("Id"))
        if source_id is None:
            rows.append({"source_id": None, "reviewable": False, "reason": "Buildium rental-owner Id must be a positive integer.", "mapped": None, "warnings": []})
            invalid += 1
            continue
        if source_id in seen:
            rows.append({"source_id": source_id, "reviewable": False, "reason": "Duplicate Buildium rental-owner Id in this dry run.", "mapped": None, "warnings": []})
            invalid += 1
            continue
        seen.add(source_id)

        active, active_error = _bool(record.get("IsActive"), field="IsActive")
        if active_error:
            rows.append({"source_id": source_id, "reviewable": False, "reason": active_error, "mapped": None, "warnings": []})
            invalid += 1
            continue
        if active is False and not include_inactive:
            rows.append({"source_id": source_id, "reviewable": False, "reason": "Inactive Buildium rental owner excluded by dry-run settings.", "mapped": None, "warnings": []})
            skipped_inactive += 1
            continue

        email, email_error = _email(record.get("Email"))
        display_name, name_error = _display_name(record)
        source_property_ids, property_ids_error = _property_ids(record.get("PropertyIds"))
        target_property_ids, property_errors = _mapped_properties(
            db,
            run=run,
            source_property_ids=source_property_ids,
        )
        errors = [x for x in (email_error, name_error, property_ids_error) if x]
        errors.extend(property_errors)
        if errors:
            rows.append({"source_id": source_id, "reviewable": False, "reason": " ".join(errors), "mapped": None, "warnings": []})
            invalid += 1
            continue

        reviewable_ids.add(source_id)
        warnings: list[str] = [
            "Buildium owner PropertyIds are reconciled to durable target Properties, but no PropertyOwner percentage or primary-owner relationship is created."
        ]
        if not source_property_ids:
            warnings.append(
                "Buildium rental owner has no PropertyIds in this source record; owner identity may be reviewed but no ownership relationship is inferred."
            )
        if active is False:
            warnings.append(
                "Inactive Buildium owner is being reviewed explicitly; matching does not deactivate the target OWNER user."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "OWNERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        candidate = (
            db.query(User)
            .filter(
                User.organization_id == run.organization_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                func.lower(User.email) == email,
            )
            .first()
        )
        if candidate is not None:
            warnings.append(
                f"Possible existing target OWNER match by exact source email: local OWNER #{candidate.id}; explicit MATCH_EXISTING review is required."
            )

        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_owner_user_id = resolution["target_owner_user_id"] if resolution else None
        if durable is not None:
            if durable.target_entity != "OWNER_USER":
                raise BuildiumOwnerMigrationError(
                    "Buildium Owner mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_owner_user_id != durable.target_id
            ):
                raise BuildiumOwnerMigrationError(
                    f"Buildium source Owner ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source Owner ID {source_id} is already durably mapped to local OWNER #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = (
                db.query(User)
                .filter(
                    User.id == target_owner_user_id,
                    User.organization_id == run.organization_id,
                    User.role == UserRole.OWNER,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise BuildiumOwnerMigrationError(
                    f"Reviewed target OWNER #{target_owner_user_id} is not an active same-organization OWNER user."
                )
            if target.email.lower() != email:
                raise BuildiumOwnerMigrationError(
                    "Reviewed OWNER email no longer matches the exact Buildium source email."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local OWNER #{target.id}; commit creates mapping metadata only."
            )
        elif action == "SKIP":
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Owner review.",
                "mapped": None,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_owner_user_id": None,
            })
            skipped_review += 1
            warning_count += len(warnings)
            continue

        rows.append({
            "source_id": source_id,
            "reviewable": True,
            "reason": None,
            "mapped": {
                "display_name": display_name,
                "email": email,
                "is_active_source": active,
                "source_property_ids": source_property_ids,
                "target_property_ids": target_property_ids,
                "target_owner_user_id": target_owner_user_id,
            },
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_owner_user_id": target_owner_user_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    unknown_resolution_ids = sorted(set(resolution_map) - reviewable_ids, key=int)
    if unknown_resolution_ids:
        raise BuildiumOwnerMigrationError(
            "Buildium Owner review decisions may reference only otherwise-valid current source rows: "
            + ", ".join(unknown_resolution_ids)
        )

    summary = {
        "resource": "OWNERS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_inactive": skipped_inactive,
        "skipped_review": skipped_review,
        "invalid": invalid,
        "warning_count": warning_count,
        "owner_users_created": False,
        "property_owner_links_created": False,
        "ownership_percentage_inferred": False,
        "tax_data_stored": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return OwnerDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        reviewable=reviewable,
        skipped_inactive=skipped_inactive,
        skipped_review=skipped_review,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


def commit_owners(
    db: Session,
    *,
    run: PlatformMigrationRun,
    include_inactive: bool,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> OwnerCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumOwnerMigrationError(
            "Commit payload, Property mapping state, or Owner review state does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumOwnerMigrationError(
            "Commit requires the exact latest successful Buildium Owner dry run."
        )
    preview = dry_run_owners(
        db,
        run=run,
        include_inactive=include_inactive,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumOwnerMigrationError(
            "Buildium Owner commit is blocked while the dry run contains invalid records."
        )

    resolution_map = _normalize_resolutions(resolutions)
    reviewable_rows = [row for row in preview.rows if row["reviewable"]]
    missing_decisions = [
        str(row["source_id"])
        for row in reviewable_rows
        if row["resolution_action"] != "MATCH_EXISTING"
        and not (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "OWNERS",
                PlatformMigrationItem.source_id == str(row["source_id"]),
            )
            .first()
        )
    ]
    if missing_decisions:
        raise BuildiumOwnerMigrationError(
            "Buildium Owner controlled mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row: "
            + ", ".join(missing_decisions)
        )

    result_rows: list[dict[str, Any]] = []
    changed = False
    matched = 0
    for row in reviewable_rows:
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "OWNERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "OWNER_USER":
                raise BuildiumOwnerMigrationError(
                    "Buildium Owner mapping is inconsistent and requires manual review."
                )
            target = (
                db.query(User)
                .filter(
                    User.id == prior.target_id,
                    User.organization_id == run.organization_id,
                    User.role == UserRole.OWNER,
                )
                .first()
            )
            if target is None:
                raise BuildiumOwnerMigrationError(
                    "A previously mapped target OWNER is missing; manual review required."
                )
            result_rows.append({"source_id": source_id, "target_owner_user_id": target.id, "replayed": True})
            continue

        decision = resolution_map[source_id]
        target_id = decision["target_owner_user_id"]
        target = (
            db.query(User)
            .filter(
                User.id == target_id,
                User.organization_id == run.organization_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise BuildiumOwnerMigrationError(
                f"Reviewed target OWNER #{target_id} is no longer active in the target organization."
            )
        if target.email.lower() != row["mapped"]["email"]:
            raise BuildiumOwnerMigrationError(
                "Reviewed target OWNER email changed after dry run; refresh review before commit."
            )
        db.add(PlatformMigrationItem(
            run_id=run.id,
            organization_id=run.organization_id,
            provider="BUILDIUM",
            resource="OWNERS",
            source_id=source_id,
            target_entity="OWNER_USER",
            target_id=target.id,
            source_fingerprint=fingerprint,
            created_by_platform_user_id=platform_user_id,
        ))
        result_rows.append({"source_id": source_id, "target_owner_user_id": target.id, "replayed": False})
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "OWNERS_MAPPED"
        db.flush()
    elif preview.skipped_review and not result_rows and run.status == "DRY_RUN_READY":
        run.status = "OWNERS_REVIEWED"
        db.flush()
        review_recorded = True

    return OwnerCommitResult(
        fingerprint=fingerprint,
        replayed=not changed and not review_recorded,
        matched_existing=matched,
        skipped_inactive=preview.skipped_inactive,
        skipped_review=preview.skipped_review,
        warning_count=preview.warning_count,
        rows=result_rows,
    )
