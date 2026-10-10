"""Buildium Work Order relationship reconciliation for Phase 4.14.

This batch reconciles Buildium Work Order identity to an already-existing
target WorkOrder only when durable Buildium Property and Unit mappings agree.
An optional Buildium Vendor relationship is enforced when it is supplied.
It never creates or updates a WorkOrder and never invents a tenant, assignee,
status transition, cost, bill, receipt, entry permission, or GL history.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder


class BuildiumWorkOrderMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class WorkOrderDryRunResult:
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
class WorkOrderCommitResult:
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


def _required_title(value: Any) -> tuple[str | None, str | None]:
    title = _clean(value)
    if title is None:
        return None, "Title is required for safe Work Order relationship reconciliation."
    if len(title) > 255:
        return None, "Title exceeds the target WorkOrder 255-character limit."
    return title, None


def _nested_id(value: Any, *keys: str) -> str | None:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _positive_id(current)


def _source_relationship_ids(
    record: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Extract only explicit property/unit IDs from provider evidence."""
    task = record.get("Task")
    property_id = (
        _positive_id(record.get("PropertyId"))
        or _nested_id(task, "PropertyId")
        or _nested_id(task, "Property", "Id")
    )
    unit_id = (
        _positive_id(record.get("UnitId"))
        or _nested_id(task, "UnitId")
        or _nested_id(task, "Unit", "Id")
    )
    vendor_raw = record.get("VendorId")
    vendor_id = None
    if vendor_raw not in (None, "", 0, "0"):
        vendor_id = _positive_id(vendor_raw)
    return property_id, unit_id, vendor_id


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
        raise BuildiumWorkOrderMigrationError(
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
        work_order_id = _positive_id(record.get("Id"))
        property_id, unit_id, vendor_id = _source_relationship_ids(record)
        item: dict[str, Any] = {
            "work_order_source_id": work_order_id,
            "property_source_id": property_id,
            "unit_source_id": unit_id,
            "vendor_source_id": vendor_id,
        }
        for key, resource, source_id, entity in (
            ("property", "PROPERTIES", property_id, "PROPERTY"),
            ("unit", "UNITS", unit_id, "UNIT"),
            ("vendor", "VENDORS", vendor_id, "VENDOR"),
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
            raise BuildiumWorkOrderMigrationError(
                "Work Order review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumWorkOrderMigrationError(
                f"Duplicate Work Order review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumWorkOrderMigrationError(
                "Work Order review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_work_order_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumWorkOrderMigrationError(
                    "MATCH_EXISTING requires a positive target Work Order ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumWorkOrderMigrationError(
                    "MATCH_EXISTING requires a positive target Work Order ID."
                )
            if target < 1:
                raise BuildiumWorkOrderMigrationError(
                    "MATCH_EXISTING requires a positive target Work Order ID."
                )
        elif target is not None:
            raise BuildiumWorkOrderMigrationError(
                "target_work_order_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_work_order_id": target,
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
        "resource": "WORK_ORDERS",
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


def _target_work_order(
    db: Session,
    *,
    run: PlatformMigrationRun,
    work_order_id: int,
) -> WorkOrder | None:
    return (
        db.query(WorkOrder)
        .join(Unit, Unit.id == WorkOrder.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            WorkOrder.id == work_order_id,
            WorkOrder.property_id == Property.id,
            Property.organization_id == run.organization_id,
            Property.deleted_at.is_(None),
        )
        .first()
    )


def dry_run_work_orders(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> WorkOrderDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumWorkOrderMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumWorkOrderMigrationError(
            "At least one Buildium Work Order record is required."
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
                    "reason": "Buildium Work Order Id must be a positive integer.",
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
                    "reason": "Duplicate Buildium Work Order Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        seen.add(source_id)

        title, title_error = _required_title(record.get("Title"))
        property_source_id, unit_source_id, vendor_source_id = (
            _source_relationship_ids(record)
        )
        vendor_raw = record.get("VendorId")
        errors = [
            item
            for item in (
                title_error,
                None if property_source_id is not None else (
                    "An explicit Buildium PropertyId is required from the Work Order or Task."
                ),
                None if unit_source_id is not None else (
                    "An explicit Buildium UnitId is required from the Work Order or Task."
                ),
                None if vendor_raw in (None, "", 0, "0") or vendor_source_id is not None else (
                    "VendorId must be a positive integer when supplied."
                ),
            )
            if item is not None
        ]
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
        vendor_mapping = (
            _mapping(
                db,
                run=run,
                resource="VENDORS",
                source_id=vendor_source_id,
                target_entity="VENDOR",
            )
            if vendor_source_id is not None
            else None
        )
        missing = []
        if property_mapping is None:
            missing.append("Property")
        if unit_mapping is None:
            missing.append("Unit")
        if vendor_source_id is not None and vendor_mapping is None:
            missing.append("Vendor")
        if missing:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": (
                        "Work Order reconciliation requires durable Buildium "
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
        vendor_row = None
        if vendor_mapping is not None:
            vendor_row = (
                db.query(Vendor)
                .filter(
                    Vendor.id == vendor_mapping.target_id,
                    Vendor.organization_id == run.organization_id,
                    Vendor.is_active.is_(True),
                    Vendor.deleted_at.is_(None),
                )
                .first()
            )
        if (
            property_row is None
            or unit_row is None
            or (vendor_source_id is not None and vendor_row is None)
        ):
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
            "This batch reconciles Buildium Work Order identity and explicit relationships only; it never creates or updates a target WorkOrder.",
            "Buildium task/work details, status, due date, priority, entry contacts, entry permission, entry notes, amount, line items, bills and vendor notes remain source evidence only and are not promoted into target maintenance or accounting facts.",
            "Target tenant_id, assigned crew, lifecycle status, entry permission, costs and financial history are never inferred from this source record.",
        ]
        candidates = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.property_id == property_row.id,
                WorkOrder.unit_id == unit_row.id,
                WorkOrder.title == title,
            )
            .order_by(WorkOrder.id.asc())
            .limit(5)
            .all()
        )
        if vendor_row is not None:
            candidates = [row for row in candidates if row.vendor_id == vendor_row.id]
        if len(candidates) == 1:
            warnings.append(
                f"Possible existing exact property/unit/title Work Order match: local Work Order #{candidates[0].id}; explicit MATCH_EXISTING review is required."
            )
        elif len(candidates) > 1:
            warnings.append(
                "Multiple target Work Orders share the mapped property/unit/title relationship; explicit review is required and no candidate is auto-selected."
            )
        else:
            warnings.append(
                "No existing target Work Order matches the explicit mapped relationships and title; this batch does not create a WorkOrder."
            )

        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "WORK_ORDERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_work_order_id"] if resolution else None

        if durable is not None:
            if durable.target_entity != "WORK_ORDER_RELATIONSHIP":
                raise BuildiumWorkOrderMigrationError(
                    "Buildium Work Order mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumWorkOrderMigrationError(
                    f"Buildium source Work Order ID {source_id} already has a durable "
                    "mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source Work Order ID {source_id} is already durably reconciled "
                f"to local Work Order #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target_work_order(db, run=run, work_order_id=target_id)
            if target is None:
                raise BuildiumWorkOrderMigrationError(
                    f"Reviewed target Work Order #{target_id} is not in the target organization."
                )
            if (
                target.property_id != property_row.id
                or target.unit_id != unit_row.id
                or target.title != title
            ):
                raise BuildiumWorkOrderMigrationError(
                    "Reviewed target Work Order no longer matches the mapped Property, Unit and exact Title contract."
                )
            if vendor_row is not None and target.vendor_id != vendor_row.id:
                raise BuildiumWorkOrderMigrationError(
                    "Reviewed target Work Order vendor does not match the current durable Buildium Vendor mapping."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Work Order #{target.id}; commit creates durable relationship mapping metadata only."
            )
        elif action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium Work Order relationship review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_work_order_id": None,
                }
            )
            skipped += 1
            warning_count += len(warnings)
            continue

        task = record.get("Task") if isinstance(record.get("Task"), dict) else {}
        rows.append(
            {
                "source_id": source_id,
                "reviewable": True,
                "reason": None,
                "mapped": {
                    "title": title,
                    "property_source_id": property_source_id,
                    "target_property_id": property_row.id,
                    "unit_source_id": unit_source_id,
                    "target_unit_id": unit_row.id,
                    "vendor_source_id": vendor_source_id,
                    "target_vendor_id": vendor_row.id if vendor_row is not None else None,
                    "task_source_id": _positive_id(task.get("Id")),
                    "source_status": _clean(record.get("Status")),
                    "source_priority": _clean(record.get("Priority")),
                    "source_due_date": _clean(record.get("DueDate")),
                    "target_work_order_id": target_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_work_order_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - valid_ids, key=int)
    if unknown:
        raise BuildiumWorkOrderMigrationError(
            "Work Order review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "WORK_ORDERS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "work_orders_created": False,
        "work_orders_updated": False,
        "tenant_inferred": False,
        "assignment_mutation": False,
        "status_mutation": False,
        "cost_mutation": False,
        "bills_created": False,
        "gl_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return WorkOrderDryRunResult(
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


def commit_work_orders(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> WorkOrderCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumWorkOrderMigrationError(
            "Commit payload, dependency mapping state or Work Order review state does not "
            "match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumWorkOrderMigrationError(
            "Commit requires the exact latest successful Buildium Work Order dry run."
        )

    preview = dry_run_work_orders(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumWorkOrderMigrationError(
            "Work Order reconciliation commit is blocked while the dry run contains invalid records."
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
                PlatformMigrationItem.resource == "WORK_ORDERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            missing.append(source_id)
    if missing:
        raise BuildiumWorkOrderMigrationError(
            "Work Order relationship mapping requires explicit MATCH_EXISTING or SKIP "
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
                PlatformMigrationItem.resource == "WORK_ORDERS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "WORK_ORDER_RELATIONSHIP":
                raise BuildiumWorkOrderMigrationError(
                    "Buildium Work Order mapping is inconsistent."
                )
            target = _target_work_order(db, run=run, work_order_id=prior.target_id)
            if target is None:
                raise BuildiumWorkOrderMigrationError(
                    "Previously reconciled target Work Order is missing or out of organization scope."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_work_order_id": target.id,
                    "replayed": True,
                }
            )
            continue

        target_id = resolution_map[source_id]["target_work_order_id"]
        target = _target_work_order(db, run=run, work_order_id=target_id)
        if target is None:
            raise BuildiumWorkOrderMigrationError(
                f"Reviewed target Work Order #{target_id} is no longer in scope."
            )
        mapped = row["mapped"]
        if (
            target.property_id != mapped["target_property_id"]
            or target.unit_id != mapped["target_unit_id"]
            or target.title != mapped["title"]
            or (
                mapped["target_vendor_id"] is not None
                and target.vendor_id != mapped["target_vendor_id"]
            )
        ):
            raise BuildiumWorkOrderMigrationError(
                "Reviewed target Work Order relationship changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="WORK_ORDERS",
                source_id=source_id,
                target_entity="WORK_ORDER_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_work_order_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "WORK_ORDERS_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "WORK_ORDERS_REVIEWED"
        db.flush()
        review_recorded = True

    return WorkOrderCommitResult(
        fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
