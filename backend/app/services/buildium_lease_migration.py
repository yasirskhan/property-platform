"""Buildium Rental Lease relationship reconciliation for Phase 4.14.

This batch reconciles Buildium lease identity to an already-existing target
Lease only when durable Buildium Property, Unit, and Tenant mappings agree.
It never creates or updates a Lease and never creates rent, deposit, invoice,
charge, payment, receipt, or GL history.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.user import User, UserRole


class BuildiumLeaseMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class LeaseDryRunResult:
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
class LeaseCommitResult:
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


def _date_value(value: Any, *, field: str) -> tuple[date | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, f"{field} is required because the target Lease requires a bounded date."
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, f"{field} must be an ISO date (YYYY-MM-DD)."


def _due_day(value: Any) -> tuple[int | None, str | None]:
    if value in (None, ""):
        return None, None
    if isinstance(value, bool):
        return None, "PaymentDueDay must be an integer from 1 through 31 when supplied."
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None, "PaymentDueDay must be an integer from 1 through 31 when supplied."
    if result < 1 or result > 31:
        return None, "PaymentDueDay must be an integer from 1 through 31 when supplied."
    return result, None


def _current_tenant_id(record: dict[str, Any]) -> tuple[str | None, str | None]:
    current = record.get("CurrentTenants")
    if current is None:
        tenants = record.get("Tenants")
        if not isinstance(tenants, list):
            return None, (
                "CurrentTenants or a Tenants collection with an explicit Active/Current "
                "status is required for safe single-tenant relationship reconciliation."
            )
        current = [
            tenant
            for tenant in tenants
            if isinstance(tenant, dict)
            and (_clean(tenant.get("Status")) or "").lower() in {"active", "current"}
        ]
    if not isinstance(current, list):
        return None, "CurrentTenants must be an array when supplied."
    if len(current) != 1:
        return None, (
            "Exactly one current Buildium tenant is required because the target Lease "
            "stores one tenant_id; multi-tenant or tenantless membership is not inferred."
        )
    tenant = current[0]
    if not isinstance(tenant, dict):
        return None, "CurrentTenants entries must be objects."
    tenant_id = _positive_id(tenant.get("Id"))
    if tenant_id is None:
        return None, "Current tenant Id must be a positive integer."
    return tenant_id, None


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
        raise BuildiumLeaseMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        lease_id = _positive_id(record.get("Id"))
        property_id = _positive_id(record.get("PropertyId"))
        unit_id = _positive_id(record.get("UnitId"))
        tenant_id, _ = _current_tenant_id(record)
        item: dict[str, Any] = {
            "lease_source_id": lease_id,
            "property_source_id": property_id,
            "unit_source_id": unit_id,
            "tenant_source_id": tenant_id,
        }
        for key, resource, source_id, entity in (
            ("property", "PROPERTIES", property_id, "PROPERTY"),
            ("unit", "UNITS", unit_id, "UNIT"),
            ("tenant", "TENANTS", tenant_id, "TENANT_USER"),
        ):
            mapped = (
                _mapping(
                    db,
                    run=run,
                    resource=resource,
                    source_id=source_id,
                    target_entity=entity,
                )
                if source_id is not None
                else None
            )
            item[key] = (
                {
                    "target_id": mapped.target_id,
                    "source_fingerprint": mapped.source_fingerprint,
                }
                if mapped is not None
                else None
            )
        result.append(item)
    return result


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumLeaseMigrationError(
                "Lease review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumLeaseMigrationError(
                f"Duplicate Lease review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumLeaseMigrationError(
                "Lease review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_lease_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumLeaseMigrationError(
                    "MATCH_EXISTING requires a positive target Lease ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumLeaseMigrationError(
                    "MATCH_EXISTING requires a positive target Lease ID."
                )
            if target < 1:
                raise BuildiumLeaseMigrationError(
                    "MATCH_EXISTING requires a positive target Lease ID."
                )
        elif target is not None:
            raise BuildiumLeaseMigrationError(
                "target_lease_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_lease_id": target,
        }
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
        "resource": "LEASES",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ],
        "dependency_mappings": _dependency_snapshot(db, run=run, records=records),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _target_lease(
    db: Session,
    *,
    run: PlatformMigrationRun,
    lease_id: int,
) -> Lease | None:
    return (
        db.query(Lease)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Lease.id == lease_id,
            Property.organization_id == run.organization_id,
            Property.deleted_at.is_(None),
        )
        .first()
    )


def dry_run_leases(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> LeaseDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumLeaseMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumLeaseMigrationError(
            "At least one Buildium Lease record is required."
        )

    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is None:
            rows.append(
                {
                    "source_id": None,
                    "reviewable": False,
                    "reason": "Buildium Lease Id must be a positive integer.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if source_id in seen:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Duplicate Buildium Lease Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        seen.add(source_id)

        property_source_id = _positive_id(record.get("PropertyId"))
        unit_source_id = _positive_id(record.get("UnitId"))
        tenant_source_id, tenant_error = _current_tenant_id(record)
        start_date, start_error = _date_value(
            record.get("LeaseFromDate"), field="LeaseFromDate"
        )
        end_date, end_error = _date_value(
            record.get("LeaseToDate"), field="LeaseToDate"
        )
        due_day, due_error = _due_day(record.get("PaymentDueDay"))
        errors = [
            item
            for item in (
                None if property_source_id is not None else "PropertyId must be a positive integer.",
                None if unit_source_id is not None else "UnitId must be a positive integer.",
                tenant_error,
                start_error,
                end_error,
                due_error,
            )
            if item is not None
        ]
        if start_date is not None and end_date is not None and end_date < start_date:
            errors.append("LeaseToDate cannot be before LeaseFromDate.")
        if errors:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": " ".join(errors),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        property_mapping = _mapping(
            db,
            run=run,
            resource="PROPERTIES",
            source_id=property_source_id,
            target_entity="PROPERTY",
        )
        unit_mapping = _mapping(
            db,
            run=run,
            resource="UNITS",
            source_id=unit_source_id,
            target_entity="UNIT",
        )
        tenant_mapping = _mapping(
            db,
            run=run,
            resource="TENANTS",
            source_id=tenant_source_id,
            target_entity="TENANT_USER",
        )
        missing = [
            label
            for label, mapping in (
                ("Property", property_mapping),
                ("Unit", unit_mapping),
                ("Tenant", tenant_mapping),
            )
            if mapping is None
        ]
        if missing:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": (
                        "Lease relationship reconciliation requires durable Buildium "
                        + ", ".join(missing)
                        + " mapping(s) in this migration run."
                    ),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        property_row = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        unit_row = (
            db.query(Unit)
            .join(Property, Property.id == Unit.property_id)
            .filter(
                Unit.id == unit_mapping.target_id,
                Unit.property_id == property_mapping.target_id,
                Unit.is_active.is_(True),
                Property.organization_id == run.organization_id,
                Property.deleted_at.is_(None),
            )
            .first()
        )
        tenant_row = (
            db.query(User)
            .filter(
                User.id == tenant_mapping.target_id,
                User.organization_id == run.organization_id,
                User.role == UserRole.TENANT,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )
        if property_row is None or unit_row is None or tenant_row is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": (
                        "One or more durable Buildium dependency mappings now point "
                        "to missing, inactive, deleted, foreign, or cross-property targets."
                    ),
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue

        valid_ids.add(source_id)
        warnings = [
            "This batch reconciles Buildium lease identity and relationships only; it never creates or updates a target Lease.",
            "Buildium rent schedules, rent amount, security deposit, status, term type, eviction flags, recurring charges, ledger transactions, move-out facts and payment history are not promoted into target financial or occupancy facts.",
        ]
        candidates = (
            db.query(Lease)
            .filter(
                Lease.unit_id == unit_row.id,
                Lease.tenant_id == tenant_row.id,
                Lease.start_date == start_date,
                Lease.end_date == end_date,
            )
            .order_by(Lease.id.asc())
            .limit(3)
            .all()
        )
        if len(candidates) == 1:
            warnings.append(
                f"Possible existing exact relationship/date Lease match: local Lease #{candidates[0].id}; explicit MATCH_EXISTING review is required."
            )
        elif len(candidates) > 1:
            warnings.append(
                "Multiple target Leases share the mapped unit, tenant and exact source dates; an explicit reviewed target is required and no candidate is auto-selected."
            )
        else:
            warnings.append(
                "No existing target Lease matches the mapped unit, tenant and exact source dates; this batch does not create a Lease."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "LEASES",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_lease_id = resolution["target_lease_id"] if resolution else None
        if durable is not None:
            if durable.target_entity != "LEASE_RELATIONSHIP":
                raise BuildiumLeaseMigrationError(
                    "Buildium Lease mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING"
                or target_lease_id != durable.target_id
            ):
                raise BuildiumLeaseMigrationError(
                    f"Buildium source Lease ID {source_id} already has a durable "
                    "mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source Lease ID {source_id} is already durably reconciled "
                f"to local Lease #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target_lease(db, run=run, lease_id=target_lease_id)
            if target is None:
                raise BuildiumLeaseMigrationError(
                    f"Reviewed target Lease #{target_lease_id} is not in the target organization."
                )
            if (
                target.unit_id != unit_row.id
                or target.tenant_id != tenant_row.id
                or target.start_date != start_date
                or target.end_date != end_date
            ):
                raise BuildiumLeaseMigrationError(
                    "Reviewed target Lease no longer matches the mapped Unit, Tenant, "
                    "LeaseFromDate and LeaseToDate relationship contract."
                )
            if due_day is not None and target.due_day != due_day:
                warnings.append(
                    f"Buildium PaymentDueDay {due_day} differs from target Lease due_day "
                    f"{target.due_day}; mapping remains relationship-only and does not overwrite it."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Lease #{target.id}; commit creates durable relationship mapping metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Lease relationship review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_lease_id": None,
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
                    "property_source_id": property_source_id,
                    "target_property_id": property_row.id,
                    "unit_source_id": unit_source_id,
                    "target_unit_id": unit_row.id,
                    "tenant_source_id": tenant_source_id,
                    "target_tenant_user_id": tenant_row.id,
                    "lease_from_date": start_date.isoformat(),
                    "lease_to_date": end_date.isoformat(),
                    "payment_due_day": due_day,
                    "lease_status": _clean(record.get("LeaseStatus")),
                    "lease_type": _clean(record.get("LeaseType")),
                    "term_type": _clean(record.get("TermType")),
                    "target_lease_id": target_lease_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_lease_id": target_lease_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - valid_ids, key=int)
    if unknown:
        raise BuildiumLeaseMigrationError(
            "Lease review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "LEASES",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "leases_created": False,
        "leases_updated": False,
        "occupancy_inferred": False,
        "rent_or_deposit_created": False,
        "charges_created": False,
        "payments_created": False,
        "gl_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return LeaseDryRunResult(
        fingerprint,
        replayed,
        len(records),
        reviewable,
        skipped,
        invalid,
        warning_count,
        rows,
        summary,
    )


def commit_leases(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> LeaseCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumLeaseMigrationError(
            "Commit payload, dependency mapping state or Lease review state does not "
            "match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumLeaseMigrationError(
            "Commit requires the exact latest successful Buildium Lease dry run."
        )

    preview = dry_run_leases(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumLeaseMigrationError(
            "Lease reconciliation commit is blocked while the dry run contains invalid records."
        )

    resolution_map = _normalize_resolutions(resolutions)
    valid = [row for row in preview.rows if row["reviewable"]]
    missing: list[str] = []
    for row in valid:
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "LEASES",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            missing.append(source_id)
    if missing:
        raise BuildiumLeaseMigrationError(
            "Lease relationship mapping requires explicit MATCH_EXISTING or SKIP "
            "review for every valid source row: "
            + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False
    for row in valid:
        source_id = str(row["source_id"])
        prior = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "LEASES",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "LEASE_RELATIONSHIP":
                raise BuildiumLeaseMigrationError("Buildium Lease mapping is inconsistent.")
            target = _target_lease(db, run=run, lease_id=prior.target_id)
            if target is None:
                raise BuildiumLeaseMigrationError(
                    "Previously reconciled target Lease is missing or out of organization scope."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_lease_id": target.id,
                    "replayed": True,
                }
            )
            continue

        target_lease_id = resolution_map[source_id]["target_lease_id"]
        target = _target_lease(db, run=run, lease_id=target_lease_id)
        if target is None:
            raise BuildiumLeaseMigrationError(
                f"Reviewed target Lease #{target_lease_id} is no longer in scope."
            )
        mapped = row["mapped"]
        if (
            target.unit_id != mapped["target_unit_id"]
            or target.tenant_id != mapped["target_tenant_user_id"]
            or target.start_date.isoformat() != mapped["lease_from_date"]
            or target.end_date.isoformat() != mapped["lease_to_date"]
        ):
            raise BuildiumLeaseMigrationError(
                "Reviewed target Lease relationship changed after dry run."
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="LEASES",
                source_id=source_id,
                target_entity="LEASE_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_lease_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "LEASES_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "LEASES_REVIEWED"
        db.flush()
        review_recorded = True

    return LeaseCommitResult(
        fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
