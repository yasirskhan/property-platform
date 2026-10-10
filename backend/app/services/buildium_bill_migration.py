"""Buildium Bill relationship reconciliation for Phase 4.14.

This batch reconciles a Buildium Bill only to an already-existing target Bill
when its explicit vendor, accounting-entity, GL-account, optional Unit and
optional Work Order relationships agree with durable Buildium mappings.

It never creates or updates a Bill, BillLine, payable posting, payment, check,
bank movement, vendor credit, markup, attachment, receipt, or GL history.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.gl_account import GLAccount
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder


class BuildiumBillMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class BillDryRunResult:
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
class BillCommitResult:
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


def _parse_date(value: Any, *, field_name: str, required: bool) -> tuple[date | None, str | None]:
    if value in (None, ""):
        if required:
            return None, f"{field_name} is required."
        return None, None
    try:
        return date.fromisoformat(str(value)), None
    except (TypeError, ValueError):
        return None, f"{field_name} must be an ISO date."


def _money(value: Any, *, field_name: str, positive: bool = True) -> tuple[Decimal | None, str | None]:
    if isinstance(value, bool):
        return None, f"{field_name} must be a decimal amount."
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field_name} must be a decimal amount."
    if not raw.is_finite():
        return None, f"{field_name} must be finite."
    quantized = raw.quantize(Decimal("0.01"))
    if raw != quantized:
        return None, f"{field_name} must have no more than two decimal places."
    if positive and quantized <= 0:
        return None, f"{field_name} must be greater than zero."
    return quantized, None


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
        raise BuildiumBillMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _line_source_ids(line: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    entity = line.get("AccountingEntity")
    if not isinstance(entity, dict):
        return None, None, None, None
    entity_type = _clean(entity.get("AccountingEntityType"))
    property_id = _positive_id(entity.get("Id")) if entity_type == "Rental" else None
    unit = entity.get("Unit")
    unit_id = _positive_id(unit.get("Id")) if isinstance(unit, dict) else None
    gl = line.get("GLAccount")
    gl_id = _positive_id(gl.get("Id")) if isinstance(gl, dict) else None
    return entity_type, property_id, unit_id, gl_id


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        bill_id = _positive_id(record.get("Id"))
        vendor_id = _positive_id(record.get("VendorId"))
        work_order_raw = record.get("WorkOrderId")
        work_order_id = (
            None if work_order_raw in (None, "", 0, "0")
            else _positive_id(work_order_raw)
        )
        item: dict[str, Any] = {
            "bill_source_id": bill_id,
            "vendor_source_id": vendor_id,
            "work_order_source_id": work_order_id,
            "vendor": None,
            "work_order": None,
            "lines": [],
        }
        if vendor_id is not None:
            mapping = _mapping(
                db, run=run, resource="VENDORS", source_id=vendor_id, target_entity="VENDOR"
            )
            if mapping is not None:
                item["vendor"] = {
                    "target_id": mapping.target_id,
                    "source_fingerprint": mapping.source_fingerprint,
                }
        if work_order_id is not None:
            mapping = _mapping(
                db,
                run=run,
                resource="WORK_ORDERS",
                source_id=work_order_id,
                target_entity="WORK_ORDER_RELATIONSHIP",
            )
            if mapping is not None:
                item["work_order"] = {
                    "target_id": mapping.target_id,
                    "source_fingerprint": mapping.source_fingerprint,
                }
        for line in record.get("Lines") if isinstance(record.get("Lines"), list) else []:
            _, property_id, unit_id, gl_id = _line_source_ids(line)
            line_item: dict[str, Any] = {
                "line_source_id": _positive_id(line.get("Id")),
                "property_source_id": property_id,
                "unit_source_id": unit_id,
                "gl_account_source_id": gl_id,
                "property": None,
                "unit": None,
                "gl_account": None,
            }
            for key, resource, source_id, entity in (
                ("property", "PROPERTIES", property_id, "PROPERTY"),
                ("unit", "UNITS", unit_id, "UNIT"),
                ("gl_account", "GL_ACCOUNTS", gl_id, "GL_ACCOUNT"),
            ):
                if source_id is None:
                    continue
                mapping = _mapping(
                    db,
                    run=run,
                    resource=resource,
                    source_id=source_id,
                    target_entity=entity,
                )
                if mapping is not None:
                    line_item[key] = {
                        "target_id": mapping.target_id,
                        "source_fingerprint": mapping.source_fingerprint,
                    }
            item["lines"].append(line_item)
        result.append(item)
    return result


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None:
            raise BuildiumBillMigrationError(
                "Bill review source_id must be a positive integer."
            )
        if source_id in result:
            raise BuildiumBillMigrationError(
                f"Duplicate Bill review decision for source ID {source_id}."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBillMigrationError(
                "Bill review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_bill_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumBillMigrationError(
                    "MATCH_EXISTING requires a positive target Bill ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumBillMigrationError(
                    "MATCH_EXISTING requires a positive target Bill ID."
                )
            if target < 1:
                raise BuildiumBillMigrationError(
                    "MATCH_EXISTING requires a positive target Bill ID."
                )
        elif target is not None:
            raise BuildiumBillMigrationError(
                "target_bill_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_bill_id": target,
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
        "resource": "BILLS",
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


def _target_bill(
    db: Session,
    *,
    run: PlatformMigrationRun,
    bill_id: int,
) -> Bill | None:
    return (
        db.query(Bill)
        .filter(
            Bill.id == bill_id,
            Bill.organization_id == run.organization_id,
            Bill.is_active.is_(True),
            Bill.deleted_at.is_(None),
            Bill.is_reversed.is_(False),
        )
        .first()
    )


def _line_signature_from_target(bill: Bill) -> Counter:
    return Counter(
        (
            int(line.gl_account_id),
            int(line.property_id) if line.property_id is not None else None,
            int(line.unit_id) if line.unit_id is not None else None,
            f"{Decimal(line.amount).quantize(Decimal('0.01')):.2f}",
        )
        for line in bill.lines
    )


def _line_signature_from_source(mapped_lines: list[dict[str, Any]]) -> Counter:
    return Counter(
        (
            int(line["target_gl_account_id"]),
            int(line["target_property_id"]),
            int(line["target_unit_id"]) if line["target_unit_id"] is not None else None,
            line["amount"],
        )
        for line in mapped_lines
    )


def _bill_matches_contract(
    bill: Bill,
    *,
    vendor_id: int,
    bill_date: date,
    due_date: date | None,
    reference_number: str | None,
    amount: Decimal,
    mapped_lines: list[dict[str, Any]],
    work_order_id: int | None,
) -> bool:
    if (
        bill.vendor_id != vendor_id
        or bill.bill_date != bill_date
        or bill.due_date != due_date
        or _clean(bill.reference_number) != reference_number
        or Decimal(bill.amount).quantize(Decimal("0.01")) != amount
    ):
        return False
    if work_order_id is not None:
        if bill.source_type != "work_order" or bill.source_id != work_order_id:
            return False
    if _line_signature_from_target(bill) != _line_signature_from_source(mapped_lines):
        return False
    return True


def _validate_source_record(
    db: Session,
    *,
    run: PlatformMigrationRun,
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Bill Id must be a positive integer.", []

    vendor_source_id = _positive_id(record.get("VendorId"))
    if vendor_source_id is None:
        return None, "Buildium Bill VendorId must be a positive integer.", []
    vendor_mapping = _mapping(
        db,
        run=run,
        resource="VENDORS",
        source_id=vendor_source_id,
        target_entity="VENDOR",
    )
    if vendor_mapping is None:
        return None, (
            f"Bill reconciliation requires durable Buildium Vendor mapping {vendor_source_id}."
        ), []
    vendor = (
        db.query(Vendor)
        .filter(
            Vendor.id == vendor_mapping.target_id,
            Vendor.organization_id == run.organization_id,
            Vendor.is_active.is_(True),
            Vendor.deleted_at.is_(None),
        )
        .first()
    )
    if vendor is None:
        return None, "Mapped Buildium Vendor is missing, inactive, deleted, or foreign.", []

    bill_date, error = _parse_date(record.get("Date"), field_name="Date", required=True)
    if error:
        return None, error, []
    due_date, error = _parse_date(record.get("DueDate"), field_name="DueDate", required=False)
    if error:
        return None, error, []

    reference_number = _clean(record.get("ReferenceNumber"))
    if reference_number is not None and len(reference_number) > 40:
        return None, "ReferenceNumber exceeds the documented Buildium 40-character limit.", []

    work_order_raw = record.get("WorkOrderId")
    work_order_source_id = (
        None if work_order_raw in (None, "", 0, "0")
        else _positive_id(work_order_raw)
    )
    if work_order_raw not in (None, "", 0, "0") and work_order_source_id is None:
        return None, "WorkOrderId must be a positive integer when supplied.", []
    work_order = None
    if work_order_source_id is not None:
        mapping = _mapping(
            db,
            run=run,
            resource="WORK_ORDERS",
            source_id=work_order_source_id,
            target_entity="WORK_ORDER_RELATIONSHIP",
        )
        if mapping is None:
            return None, (
                f"Bill reconciliation requires durable Buildium Work Order mapping {work_order_source_id}."
            ), []
        work_order = (
            db.query(WorkOrder)
            .filter(WorkOrder.id == mapping.target_id)
            .first()
        )
        if work_order is None:
            return None, "Mapped Buildium Work Order no longer exists.", []

    lines = record.get("Lines")
    if not isinstance(lines, list) or not lines:
        return None, "Buildium Bill requires at least one line.", []
    if len(lines) > 500:
        return None, "Buildium Bill line count exceeds the bounded 500-line migration limit.", []

    mapped_lines: list[dict[str, Any]] = []
    seen_line_ids: set[str] = set()
    total = Decimal("0.00")
    warnings = [
        "This batch reconciles Buildium Bill identity and explicit line relationships only; it never creates or updates a target Bill or BillLine.",
        "Buildium paid status/date, approval status, memo, line memo, files, payments, vendor credits and payment allocation history remain source evidence only.",
        "Target payable account, cash account, owner scope and payment history are not inferred from the Buildium Bill record.",
    ]

    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            return None, f"Bill line {index} must be an object.", []
        line_id = _positive_id(line.get("Id"))
        if line_id is None:
            return None, f"Bill line {index} Id must be a positive integer.", []
        if line_id in seen_line_ids:
            return None, f"Duplicate Buildium Bill line Id {line_id}.", []
        seen_line_ids.add(line_id)

        entity_type, property_source_id, unit_source_id, gl_source_id = _line_source_ids(line)
        if entity_type != "Rental":
            return None, (
                f"Bill line {line_id} AccountingEntityType {entity_type or 'missing'} is not supported; "
                "this bounded batch reconciles Rental accounting entities only."
            ), []
        if property_source_id is None:
            return None, f"Bill line {line_id} requires a positive Rental AccountingEntity Id.", []
        if gl_source_id is None:
            return None, f"Bill line {line_id} requires a positive GLAccount Id.", []

        property_mapping = _mapping(
            db,
            run=run,
            resource="PROPERTIES",
            source_id=property_source_id,
            target_entity="PROPERTY",
        )
        if property_mapping is None:
            return None, (
                f"Bill line {line_id} requires durable Buildium Property mapping {property_source_id}."
            ), []
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
        if property_row is None:
            return None, f"Bill line {line_id} mapped Property is no longer active and in scope.", []

        unit_row = None
        if unit_source_id is not None:
            unit_mapping = _mapping(
                db,
                run=run,
                resource="UNITS",
                source_id=unit_source_id,
                target_entity="UNIT",
            )
            if unit_mapping is None:
                return None, (
                    f"Bill line {line_id} requires durable Buildium Unit mapping {unit_source_id}."
                ), []
            unit_row = (
                db.query(Unit)
                .filter(
                    Unit.id == unit_mapping.target_id,
                    Unit.property_id == property_row.id,
                    Unit.is_active.is_(True),
                )
                .first()
            )
            if unit_row is None:
                return None, (
                    f"Bill line {line_id} mapped Unit is missing, inactive, or does not belong to the mapped Property."
                ), []

        gl_mapping = _mapping(
            db,
            run=run,
            resource="GL_ACCOUNTS",
            source_id=gl_source_id,
            target_entity="GL_ACCOUNT",
        )
        if gl_mapping is None:
            return None, (
                f"Bill line {line_id} requires durable Buildium GL Account mapping {gl_source_id}."
            ), []
        gl_row = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
            )
            .first()
        )
        if gl_row is None:
            return None, f"Bill line {line_id} mapped GL Account is no longer in organization scope.", []

        amount, error = _money(line.get("Amount"), field_name=f"Bill line {line_id} Amount")
        if error:
            return None, error, []

        markup = line.get("Markup")
        if markup not in (None, {}):
            if not isinstance(markup, dict):
                return None, f"Bill line {line_id} Markup must be an object when supplied.", []
            markup_amount = markup.get("Amount")
            if markup_amount not in (None, "", 0, 0.0, "0", "0.00"):
                parsed_markup, markup_error = _money(
                    markup_amount,
                    field_name=f"Bill line {line_id} Markup.Amount",
                    positive=False,
                )
                if markup_error:
                    return None, markup_error, []
                if parsed_markup != Decimal("0.00"):
                    return None, (
                        f"Bill line {line_id} contains a non-zero Buildium markup that the target BillLine contract "
                        "does not independently represent."
                    ), []
            warnings.append(
                f"Buildium Bill line {line_id} markup metadata is retained as source evidence only and is not promoted."
            )

        total += amount
        mapped_lines.append(
            {
                "source_line_id": line_id,
                "property_source_id": property_source_id,
                "target_property_id": property_row.id,
                "unit_source_id": unit_source_id,
                "target_unit_id": unit_row.id if unit_row is not None else None,
                "gl_account_source_id": gl_source_id,
                "target_gl_account_id": gl_row.id,
                "amount": f"{amount:.2f}",
            }
        )

    return {
        "source_id": source_id,
        "vendor_source_id": vendor_source_id,
        "target_vendor_id": vendor.id,
        "bill_date": bill_date,
        "due_date": due_date,
        "reference_number": reference_number,
        "amount": total.quantize(Decimal("0.01")),
        "work_order_source_id": work_order_source_id,
        "target_work_order_id": work_order.id if work_order is not None else None,
        "mapped_lines": mapped_lines,
        "source_paid_status": _clean(record.get("PaidStatus")),
        "source_paid_date": _clean(record.get("PaidDate")),
        "source_approval_status": _clean(record.get("ApprovalStatus")),
    }, None, warnings


def dry_run_bills(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> BillDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumBillMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumBillMigrationError("At least one Buildium Bill record is required.")

    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    resolution_map = _normalize_resolutions(resolutions)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is None:
            rows.append({
                "source_id": None,
                "reviewable": False,
                "reason": "Buildium Bill Id must be a positive integer.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        if source_id in seen:
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Duplicate Buildium Bill Id in this dry run.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        seen.add(source_id)

        mapped, error, warnings = _validate_source_record(db, run=run, record=record)
        if error is not None:
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": error,
                "mapped": None,
                "warnings": warnings,
            })
            invalid += 1
            warning_count += len(warnings)
            continue

        valid_ids.add(source_id)
        durable = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "BUILDIUM",
                PlatformMigrationItem.resource == "BILLS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_bill_id"] if resolution else None

        candidates = (
            db.query(Bill)
            .filter(
                Bill.organization_id == run.organization_id,
                Bill.vendor_id == mapped["target_vendor_id"],
                Bill.bill_date == mapped["bill_date"],
                Bill.amount == mapped["amount"],
                Bill.is_active.is_(True),
                Bill.deleted_at.is_(None),
                Bill.is_reversed.is_(False),
            )
            .order_by(Bill.id.asc())
            .limit(20)
            .all()
        )
        candidates = [
            bill for bill in candidates
            if _bill_matches_contract(
                bill,
                vendor_id=mapped["target_vendor_id"],
                bill_date=mapped["bill_date"],
                due_date=mapped["due_date"],
                reference_number=mapped["reference_number"],
                amount=mapped["amount"],
                mapped_lines=mapped["mapped_lines"],
                work_order_id=mapped["target_work_order_id"],
            )
        ]
        if len(candidates) == 1:
            warnings.append(
                f"Possible existing exact Buildium Bill relationship match: local Bill #{candidates[0].id}; explicit MATCH_EXISTING review is required."
            )
        elif len(candidates) > 1:
            warnings.append(
                "Multiple target Bills satisfy the exact reviewed vendor/date/reference/line-allocation contract; no candidate is auto-selected."
            )
        else:
            warnings.append(
                "No existing target Bill satisfies the exact reviewed relationship contract; this batch does not create a Bill."
            )

        if durable is not None:
            if durable.target_entity != "BILL_RELATIONSHIP":
                raise BuildiumBillMigrationError(
                    "Buildium Bill mapping is inconsistent and requires manual review."
                )
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumBillMigrationError(
                    f"Buildium source Bill ID {source_id} already has a durable mapping and cannot be re-resolved."
                )
            warnings.append(
                f"Buildium source Bill ID {source_id} is already durably reconciled to local Bill #{durable.target_id}; commit will replay."
            )

        if action == "MATCH_EXISTING":
            target = _target_bill(db, run=run, bill_id=target_id)
            if target is None:
                raise BuildiumBillMigrationError(
                    f"Reviewed target Bill #{target_id} is not active in the target organization."
                )
            if not _bill_matches_contract(
                target,
                vendor_id=mapped["target_vendor_id"],
                bill_date=mapped["bill_date"],
                due_date=mapped["due_date"],
                reference_number=mapped["reference_number"],
                amount=mapped["amount"],
                mapped_lines=mapped["mapped_lines"],
                work_order_id=mapped["target_work_order_id"],
            ):
                raise BuildiumBillMigrationError(
                    "Reviewed target Bill no longer matches the exact mapped Buildium Bill relationship contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Bill #{target.id}; commit creates durable relationship mapping metadata only."
            )
        elif action == "SKIP":
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Bill relationship review.",
                "mapped": None,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_bill_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue

        rows.append({
            "source_id": source_id,
            "reviewable": True,
            "reason": None,
            "mapped": {
                "target_vendor_id": mapped["target_vendor_id"],
                "bill_date": mapped["bill_date"].isoformat(),
                "due_date": mapped["due_date"].isoformat() if mapped["due_date"] else None,
                "reference_number": mapped["reference_number"],
                "amount": f"{mapped['amount']:.2f}",
                "target_work_order_id": mapped["target_work_order_id"],
                "lines": mapped["mapped_lines"],
                "source_paid_status": mapped["source_paid_status"],
                "source_paid_date": mapped["source_paid_date"],
                "source_approval_status": mapped["source_approval_status"],
                "target_bill_id": target_id,
            },
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_bill_id": target_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - valid_ids, key=int)
    if unknown:
        raise BuildiumBillMigrationError(
            "Bill review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "BILLS",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "bills_created": False,
        "bills_updated": False,
        "bill_lines_created": False,
        "payable_posting_created": False,
        "payments_created": False,
        "checks_created": False,
        "bank_movement_created": False,
        "vendor_credits_created": False,
        "gl_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return BillDryRunResult(
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


def commit_bills(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> BillCommitResult:
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if expected_fingerprint != fingerprint:
        raise BuildiumBillMigrationError(
            "Commit payload, dependency mapping state or Bill review state does not match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumBillMigrationError(
            "Commit requires the exact latest successful Buildium Bill dry run."
        )

    preview = dry_run_bills(db, run=run, records=records, resolutions=resolutions)
    if preview.invalid:
        raise BuildiumBillMigrationError(
            "Bill reconciliation commit is blocked while the dry run contains invalid records."
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
                PlatformMigrationItem.resource == "BILLS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            missing.append(source_id)
    if missing:
        raise BuildiumBillMigrationError(
            "Bill relationship mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row: "
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
                PlatformMigrationItem.resource == "BILLS",
                PlatformMigrationItem.source_id == source_id,
            )
            .first()
        )
        if prior is not None:
            if prior.target_entity != "BILL_RELATIONSHIP":
                raise BuildiumBillMigrationError("Buildium Bill mapping is inconsistent.")
            target = _target_bill(db, run=run, bill_id=prior.target_id)
            if target is None:
                raise BuildiumBillMigrationError(
                    "Previously reconciled target Bill is missing, reversed, inactive, deleted, or out of organization scope."
                )
            rows.append({
                "source_id": source_id,
                "target_bill_id": target.id,
                "replayed": True,
            })
            continue

        target_id = resolution_map[source_id]["target_bill_id"]
        target = _target_bill(db, run=run, bill_id=target_id)
        if target is None:
            raise BuildiumBillMigrationError(
                f"Reviewed target Bill #{target_id} is no longer active and in scope."
            )

        mapped, error, _ = _validate_source_record(db, run=run, record=next(
            record for record in records if _positive_id(record.get("Id")) == source_id
        ))
        if error is not None or mapped is None:
            raise BuildiumBillMigrationError(
                "Buildium Bill source relationship changed after dry run."
            )
        if not _bill_matches_contract(
            target,
            vendor_id=mapped["target_vendor_id"],
            bill_date=mapped["bill_date"],
            due_date=mapped["due_date"],
            reference_number=mapped["reference_number"],
            amount=mapped["amount"],
            mapped_lines=mapped["mapped_lines"],
            work_order_id=mapped["target_work_order_id"],
        ):
            raise BuildiumBillMigrationError(
                "Reviewed target Bill relationship changed after dry run."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BILLS",
                source_id=source_id,
                target_entity="BILL_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_id": source_id,
            "target_bill_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "BILLS_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "BILLS_REVIEWED"
        db.flush()
        review_recorded = True

    return BillCommitResult(
        fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
