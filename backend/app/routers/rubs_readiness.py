"""Phase 4.5 readiness plus Phase 4.9 raw RUBs meter readings.

Meter readings are source inputs only. They do not establish an allocation
formula, legal eligibility, a tenant/owner obligation, a utility charge, or
an accounting entry.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.property import Property, PropertyAssignment, Unit
from app.models.utility import (
    PaidBy,
    PropertyUtility,
    UtilityBill,
    UtilityMeterReading,
    UtilityAllocationRuleRevision,
)
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.utility import (
    MeterReadingCreate,
    MeterReadingCSVImport,
    MeterReadingImportResult,
    MeterReadingImportRow,
    MeterReadingOut,
    AllocationRuleAuthorize,
    AllocationRuleCreate,
    AllocationRuleOut,
    AllocationPreviewRequest,
)
from app.services.menu_resolver import permission_allows_user
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/properties", tags=["RUBs readiness"])
FEATURE_KEY = "release.properties.rubs"
MAX_SHARED_UTILITIES = 100
MAX_PREVIEW_BILLS = 500
MAX_METER_READINGS = 500
MAX_IMPORT_ROWS = 250


def _rubs_property(db: Session, current_user: User, property_id: int) -> Property:
    if (
        current_user.organization_id is None
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role
        not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or not permission_allows_user(
            db, user=current_user, menu_key="PROPERTIES.ALL"
        )
    ):
        raise HTTPException(status_code=403, detail="Property permission required.")

    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="RUBs is not available.")

    prop = (
        db.query(Property)
        .filter(
            Property.id == property_id,
            Property.organization_id == current_user.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
        .first()
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found.")

    if current_user.role == UserRole.MANAGER and not (
        db.query(PropertyAssignment.id)
        .filter(
            PropertyAssignment.property_id == prop.id,
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        .first()
    ):
        raise HTTPException(status_code=404, detail="Property not found.")

    return prop


def _shared_utility(
    db: Session, *, property_id: int, utility_id: int
) -> PropertyUtility:
    utility = (
        db.query(PropertyUtility)
        .filter(
            PropertyUtility.id == utility_id,
            PropertyUtility.property_id == property_id,
            PropertyUtility.is_active.is_(True),
            PropertyUtility.deleted_at.is_(None),
            PropertyUtility.paid_by == PaidBy.SHARED,
        )
        .first()
    )
    if utility is None:
        raise HTTPException(status_code=404, detail="Shared utility not found.")
    return utility


def _validate_unit_ids(
    db: Session, *, property_id: int, unit_ids: set[int]
) -> None:
    if not unit_ids:
        return
    rows = (
        db.query(Unit.id)
        .filter(
            Unit.id.in_(unit_ids),
            Unit.property_id == property_id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
        .all()
    )
    found = {row[0] for row in rows}
    if found != unit_ids:
        raise HTTPException(
            status_code=422,
            detail="One or more unit IDs are not active for this property.",
        )


def _same_reading(
    reading: UtilityMeterReading,
    payload: MeterReadingCreate | MeterReadingImportRow,
    *,
    source: str,
    import_batch_key: str | None,
) -> bool:
    return (
        reading.source == source
        and reading.import_batch_key == import_batch_key
        and reading.unit_id == payload.unit_id
        and reading.meter_identifier == payload.meter_identifier
        and reading.reading_date == payload.reading_date
        and Decimal(reading.reading_value) == Decimal(payload.reading_value)
        and reading.unit_of_measure == payload.unit_of_measure
        and (reading.notes or None) == (payload.notes or None)
        and reading.is_active
    )


@router.get("/{property_id}/rubs-readiness")
def rubs_readiness(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    utilities = (
        db.query(PropertyUtility)
        .filter(
            PropertyUtility.property_id == prop.id,
            PropertyUtility.is_active.is_(True),
            PropertyUtility.deleted_at.is_(None),
            PropertyUtility.paid_by == PaidBy.SHARED,
        )
        .order_by(PropertyUtility.id)
        .limit(MAX_SHARED_UTILITIES + 1)
        .all()
    )
    if len(utilities) > MAX_SHARED_UTILITIES:
        raise HTTPException(
            status_code=422, detail="Too many shared utilities for preview."
        )

    ids = [u.id for u in utilities]
    bills = (
        db.query(UtilityBill)
        .filter(UtilityBill.utility_id.in_(ids))
        .order_by(UtilityBill.id.desc())
        .limit(MAX_PREVIEW_BILLS + 1)
        .all()
        if ids
        else []
    )
    if len(bills) > MAX_PREVIEW_BILLS:
        raise HTTPException(
            status_code=422, detail="Too many utility bills for preview."
        )

    by_utility: dict[int, dict[str, object]] = {}
    for utility in utilities:
        by_utility[utility.id] = {
            "utility_id": utility.id,
            "utility_type": utility.utility_type.value,
            "bill_count": 0,
            "periods_complete": 0,
            "periods_missing_or_invalid": 0,
            "periods_overlapping": 0,
            "periods_duplicate": 0,
        }

    for bill in bills:
        item = by_utility[bill.utility_id]
        item["bill_count"] += 1
        if (
            bill.billing_period_start is not None
            and bill.billing_period_end is not None
            and bill.billing_period_start <= bill.billing_period_end
        ):
            item["periods_complete"] += 1
        else:
            item["periods_missing_or_invalid"] += 1

    periods_by_utility: dict[int, list[tuple[object, object]]] = {
        uid: [] for uid in ids
    }
    for bill in bills:
        start, end = bill.billing_period_start, bill.billing_period_end
        if start is not None and end is not None and start <= end:
            periods_by_utility[bill.utility_id].append((start, end))

    for uid, periods in periods_by_utility.items():
        latest_end = None
        seen: set[tuple[object, object]] = set()
        for start, end in sorted(periods):
            if latest_end is not None and start <= latest_end:
                by_utility[uid]["periods_overlapping"] += 1
            if (start, end) in seen:
                by_utility[uid]["periods_duplicate"] += 1
            seen.add((start, end))
            if latest_end is None or end > latest_end:
                latest_end = end

    response.headers["Cache-Control"] = "no-store"
    return {
        "property_id": prop.id,
        "utility_count": len(by_utility),
        "items": list(by_utility.values()),
        "meter_readings_available": True,
        "allocation_available": False,
        "billing_available": False,
        "meaning": (
            "Shared-utility inventory plus raw meter-reading capture. "
            "Recorded readings are source data only and do not establish "
            "an allocation method, tenant charge, owner charge, or regulatory compliance."
        ),
    }


@router.get(
    "/{property_id}/rubs/utilities/{utility_id}/meter-readings",
    response_model=list[MeterReadingOut],
)
def list_meter_readings(
    property_id: int,
    utility_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    rows = (
        db.query(UtilityMeterReading)
        .filter(
            UtilityMeterReading.utility_id == utility_id,
            UtilityMeterReading.is_active.is_(True),
        )
        .order_by(
            UtilityMeterReading.reading_date.desc(),
            UtilityMeterReading.id.desc(),
        )
        .limit(MAX_METER_READINGS + 1)
        .all()
    )
    if len(rows) > MAX_METER_READINGS:
        raise HTTPException(
            status_code=422, detail="Too many meter readings for this view."
        )
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.post(
    "/{property_id}/rubs/utilities/{utility_id}/meter-readings",
    response_model=MeterReadingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_meter_reading(
    property_id: int,
    utility_id: int,
    payload: MeterReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    if payload.unit_id is not None:
        _validate_unit_ids(
            db, property_id=prop.id, unit_ids={payload.unit_id}
        )

    request_key = f"manual:{payload.request_key}"
    existing = (
        db.query(UtilityMeterReading)
        .filter(
            UtilityMeterReading.utility_id == utility_id,
            UtilityMeterReading.request_key == request_key,
        )
        .first()
    )
    if existing is not None:
        if not _same_reading(
            existing, payload, source="MANUAL", import_batch_key=None
        ):
            raise HTTPException(
                status_code=409,
                detail="Meter-reading request key was already used for different data.",
            )
        return existing

    row = UtilityMeterReading(
        utility_id=utility_id,
        unit_id=payload.unit_id,
        meter_identifier=payload.meter_identifier,
        reading_date=payload.reading_date,
        reading_value=payload.reading_value,
        unit_of_measure=payload.unit_of_measure,
        source="MANUAL",
        import_batch_key=None,
        request_key=request_key,
        notes=payload.notes,
        created_by_id=current_user.id,
        is_active=True,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Meter-reading request was already processed; retry the original request.",
        )
    db.refresh(row)
    log_action(
        db,
        current_user,
        entity_type="utility_meter_reading",
        entity_id=row.id,
        action="created",
        new_value={"utility_id": utility_id, "source": "MANUAL"},
    )
    return row


def _parse_csv(payload: MeterReadingCSVImport) -> list[tuple[int, MeterReadingImportRow]]:
    try:
        reader = csv.DictReader(io.StringIO(payload.csv_text))
    except csv.Error as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {exc}")

    if reader.fieldnames is None:
        raise HTTPException(status_code=422, detail="CSV header row is required.")

    normalized: dict[str, str] = {}
    for original in reader.fieldnames:
        key = (original or "").strip().lstrip("\ufeff").lower()
        if not key or key in normalized:
            raise HTTPException(status_code=422, detail="CSV headers must be unique.")
        normalized[key] = original

    required = {
        "meter_identifier",
        "reading_date",
        "reading_value",
        "unit_of_measure",
    }
    allowed = required | {"unit_id", "notes"}
    missing = sorted(required - normalized.keys())
    unexpected = sorted(normalized.keys() - allowed)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV is missing required columns: {', '.join(missing)}.",
        )
    if unexpected:
        raise HTTPException(
            status_code=422,
            detail=f"CSV contains unsupported columns: {', '.join(unexpected)}.",
        )

    parsed: list[tuple[int, MeterReadingImportRow]] = []
    try:
        for csv_line, raw in enumerate(reader, start=2):
            values = {
                key: (raw.get(original) or "").strip()
                for key, original in normalized.items()
            }
            if not any(values.values()):
                continue
            if len(parsed) >= MAX_IMPORT_ROWS:
                raise HTTPException(
                    status_code=422,
                    detail=f"CSV import is limited to {MAX_IMPORT_ROWS} readings.",
                )
            try:
                reading_date = date.fromisoformat(values["reading_date"])
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"CSV row {csv_line} has an invalid reading_date; use YYYY-MM-DD.",
                )
            try:
                reading_value = Decimal(values["reading_value"])
            except (InvalidOperation, ValueError):
                raise HTTPException(
                    status_code=422,
                    detail=f"CSV row {csv_line} has an invalid reading_value.",
                )
            if not reading_value.is_finite():
                raise HTTPException(
                    status_code=422,
                    detail=f"CSV row {csv_line} has an invalid reading_value.",
                )
            unit_id = None
            if values.get("unit_id"):
                try:
                    unit_id = int(values["unit_id"])
                except ValueError:
                    raise HTTPException(
                        status_code=422,
                        detail=f"CSV row {csv_line} has an invalid unit_id.",
                    )
            try:
                row = MeterReadingImportRow(
                    meter_identifier=values["meter_identifier"],
                    reading_date=reading_date,
                    reading_value=reading_value,
                    unit_of_measure=values["unit_of_measure"],
                    unit_id=unit_id,
                    notes=values.get("notes") or None,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"CSV row {csv_line} is invalid: {exc}",
                )
            parsed.append((csv_line, row))
    except csv.Error as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {exc}")

    if not parsed:
        raise HTTPException(status_code=422, detail="CSV contains no meter readings.")
    return parsed


@router.post(
    "/{property_id}/rubs/utilities/{utility_id}/meter-readings/import",
    response_model=MeterReadingImportResult,
)
def import_meter_readings_csv(
    property_id: int,
    utility_id: int,
    payload: MeterReadingCSVImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    parsed = _parse_csv(payload)
    _validate_unit_ids(
        db,
        property_id=prop.id,
        unit_ids={row.unit_id for _, row in parsed if row.unit_id is not None},
    )

    existing_batch = (
        db.query(UtilityMeterReading)
        .filter(
            UtilityMeterReading.utility_id == utility_id,
            UtilityMeterReading.import_batch_key == payload.request_key,
        )
        .order_by(UtilityMeterReading.id)
        .all()
    )
    if existing_batch:
        expected = {
            f"import:{payload.request_key}:{csv_line}": row
            for csv_line, row in parsed
        }
        by_key = {row.request_key: row for row in existing_batch}
        if set(by_key) != set(expected):
            raise HTTPException(
                status_code=409,
                detail="Import request key was already used for a different CSV batch.",
            )
        for request_key, parsed_row in expected.items():
            if not _same_reading(
                by_key[request_key],
                parsed_row,
                source="IMPORT",
                import_batch_key=payload.request_key,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Import request key was already used for different data.",
                )
        return {
            "created": 0,
            "replayed": len(existing_batch),
            "total": len(existing_batch),
            "readings": existing_batch,
        }

    created: list[UtilityMeterReading] = []
    for csv_line, parsed_row in parsed:
        row = UtilityMeterReading(
            utility_id=utility_id,
            unit_id=parsed_row.unit_id,
            meter_identifier=parsed_row.meter_identifier,
            reading_date=parsed_row.reading_date,
            reading_value=parsed_row.reading_value,
            unit_of_measure=parsed_row.unit_of_measure,
            source="IMPORT",
            import_batch_key=payload.request_key,
            request_key=f"import:{payload.request_key}:{csv_line}",
            notes=parsed_row.notes,
            created_by_id=current_user.id,
            is_active=True,
        )
        db.add(row)
        created.append(row)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Meter-reading import was already processed; retry the original batch.",
        )
    for row in created:
        db.refresh(row)

    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="rubs_meter_readings_imported",
        new_value={"utility_id": utility_id, "count": len(created)},
    )
    return {
        "created": len(created),
        "replayed": 0,
        "total": len(created),
        "readings": created,
    }


# ------------------------------------------------------------
# Phase 4.9 versioned allocation rules and finance-neutral preview
# ------------------------------------------------------------
ALLOCATION_BASES = {"SQUARE_FEET", "OCCUPANCY", "FIXTURES", "MANUAL_WEIGHT"}
MAX_ALLOCATION_UNITS = 500


def _rule_out(row: UtilityAllocationRuleRevision) -> dict[str, object]:
    return {
        "id": row.id,
        "utility_id": row.utility_id,
        "revision_number": row.revision_number,
        "effective_date": row.effective_date,
        "basis": row.basis,
        "unit_inputs": json.loads(row.unit_inputs_json),
        "status": row.status,
        "is_authorized": bool(row.is_authorized),
        "authorized_at": row.authorized_at,
        "created_at": row.created_at,
    }


def _allocation_units(db: Session, *, property_id: int, unit_ids: list[int]) -> list[Unit]:
    if len(unit_ids) != len(set(unit_ids)):
        raise HTTPException(status_code=422, detail="Allocation units must be unique.")
    if not unit_ids or len(unit_ids) > MAX_ALLOCATION_UNITS:
        raise HTTPException(
            status_code=422,
            detail=f"Select between 1 and {MAX_ALLOCATION_UNITS} active units.",
        )
    rows = (
        db.query(Unit)
        .filter(
            Unit.id.in_(unit_ids),
            Unit.property_id == property_id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
        .all()
    )
    by_id = {row.id: row for row in rows}
    if set(by_id) != set(unit_ids):
        raise HTTPException(
            status_code=422,
            detail="One or more allocation units are not active for this property.",
        )
    return [by_id[unit_id] for unit_id in sorted(unit_ids)]


@router.get("/{property_id}/rubs/utilities/{utility_id}/allocation-context")
def allocation_context(
    property_id: int,
    utility_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    units = (
        db.query(Unit)
        .filter(
            Unit.property_id == prop.id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
        .order_by(Unit.unit_number, Unit.id)
        .limit(MAX_ALLOCATION_UNITS + 1)
        .all()
    )
    if len(units) > MAX_ALLOCATION_UNITS:
        raise HTTPException(status_code=422, detail="Too many active units for RUBs preview.")
    bills = (
        db.query(UtilityBill)
        .filter(UtilityBill.utility_id == utility_id)
        .order_by(UtilityBill.billing_period_end.desc(), UtilityBill.id.desc())
        .limit(MAX_PREVIEW_BILLS + 1)
        .all()
    )
    if len(bills) > MAX_PREVIEW_BILLS:
        raise HTTPException(status_code=422, detail="Too many utility bills for RUBs preview.")
    response.headers["Cache-Control"] = "no-store"
    return {
        "property_id": prop.id,
        "utility_id": utility_id,
        "units": [
            {"id": unit.id, "unit_number": unit.unit_number, "square_feet": unit.square_feet}
            for unit in units
        ],
        "bills": [
            {
                "id": bill.id,
                "billing_period_start": bill.billing_period_start,
                "billing_period_end": bill.billing_period_end,
                "amount": bill.amount,
                "period_valid": (
                    bill.billing_period_start is not None
                    and bill.billing_period_end is not None
                    and bill.billing_period_start <= bill.billing_period_end
                ),
            }
            for bill in bills
        ],
        "meaning": (
            "Allocation context is source data for an explicit staff-reviewed rule. "
            "It does not identify legally eligible occupants or create a charge."
        ),
    }


@router.get(
    "/{property_id}/rubs/utilities/{utility_id}/allocation-rules",
    response_model=list[AllocationRuleOut],
)
def list_allocation_rules(
    property_id: int,
    utility_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    rows = (
        db.query(UtilityAllocationRuleRevision)
        .filter(UtilityAllocationRuleRevision.utility_id == utility_id)
        .order_by(UtilityAllocationRuleRevision.revision_number.desc())
        .limit(100)
        .all()
    )
    response.headers["Cache-Control"] = "no-store"
    return [_rule_out(row) for row in rows]


@router.post(
    "/{property_id}/rubs/utilities/{utility_id}/allocation-rules",
    response_model=AllocationRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_allocation_rule(
    property_id: int,
    utility_id: int,
    payload: AllocationRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    utility = (
        db.query(PropertyUtility)
        .filter(
            PropertyUtility.id == utility_id,
            PropertyUtility.property_id == prop.id,
            PropertyUtility.is_active.is_(True),
            PropertyUtility.deleted_at.is_(None),
            PropertyUtility.paid_by == PaidBy.SHARED,
        )
        .with_for_update()
        .first()
    )
    if utility is None:
        raise HTTPException(status_code=404, detail="Shared utility not found.")

    existing = (
        db.query(UtilityAllocationRuleRevision)
        .filter(
            UtilityAllocationRuleRevision.utility_id == utility_id,
            UtilityAllocationRuleRevision.request_key == payload.request_key,
        )
        .first()
    )
    basis = payload.basis.upper()
    if basis not in ALLOCATION_BASES:
        raise HTTPException(status_code=422, detail="Unsupported RUBs allocation basis.")

    requested_by_id = {item.unit_id: item for item in payload.units}
    if len(requested_by_id) != len(payload.units):
        raise HTTPException(status_code=422, detail="Allocation units must be unique.")
    units = _allocation_units(db, property_id=prop.id, unit_ids=list(requested_by_id))

    snapshot = []
    for unit in units:
        requested = requested_by_id[unit.id]
        if basis == "SQUARE_FEET":
            if requested.weight is not None:
                raise HTTPException(
                    status_code=422,
                    detail="SQUARE_FEET uses recorded unit square footage; omit manual weights.",
                )
            if unit.square_feet is None or unit.square_feet <= 0:
                raise HTTPException(
                    status_code=422,
                    detail="Every selected unit requires positive recorded square feet.",
                )
            weight = Decimal(unit.square_feet)
        else:
            if requested.weight is None or requested.weight <= 0:
                raise HTTPException(
                    status_code=422,
                    detail=f"{basis} requires an explicit positive weight for every selected unit.",
                )
            weight = Decimal(requested.weight)
        snapshot.append({"unit_id": unit.id, "weight": str(weight)})

    snapshot_json = json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
    if existing is not None:
        if (
            existing.basis != basis
            or existing.effective_date != payload.effective_date
            or existing.unit_inputs_json != snapshot_json
        ):
            raise HTTPException(
                status_code=409,
                detail="Allocation-rule request key was already used for different data.",
            )
        return _rule_out(existing)

    latest = (
        db.query(UtilityAllocationRuleRevision)
        .filter(UtilityAllocationRuleRevision.utility_id == utility_id)
        .order_by(UtilityAllocationRuleRevision.revision_number.desc())
        .first()
    )
    row = UtilityAllocationRuleRevision(
        utility_id=utility_id,
        revision_number=(latest.revision_number + 1) if latest else 1,
        effective_date=payload.effective_date,
        basis=basis,
        unit_inputs_json=snapshot_json,
        request_key=payload.request_key,
        status="DRAFT",
        is_authorized=False,
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Allocation-rule revision changed concurrently; retry with the same request key.",
        )
    db.refresh(row)
    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="rubs_allocation_rule_created",
        new_value={
            "utility_id": utility_id,
            "revision_number": row.revision_number,
            "basis": basis,
            "authorized": False,
        },
    )
    return _rule_out(row)


@router.post(
    "/{property_id}/rubs/utilities/{utility_id}/allocation-rules/{rule_id}/authorize",
    response_model=AllocationRuleOut,
)
def authorize_allocation_rule(
    property_id: int,
    utility_id: int,
    rule_id: int,
    payload: AllocationRuleAuthorize,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    row = (
        db.query(UtilityAllocationRuleRevision)
        .filter(
            UtilityAllocationRuleRevision.id == rule_id,
            UtilityAllocationRuleRevision.utility_id == utility_id,
        )
        .with_for_update()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Allocation-rule revision not found.")
    if row.is_authorized:
        if (
            row.authorization_request_key is not None
            and row.authorization_request_key != payload.request_key
        ):
            raise HTTPException(
                status_code=409,
                detail="This rule revision was already authorized by another request.",
            )
        return _rule_out(row)

    row.is_authorized = True
    row.status = "AUTHORIZED"
    row.authorization_request_key = payload.request_key
    row.authorized_by_id = current_user.id
    row.authorized_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="rubs_allocation_rule_authorized",
        new_value={
            "utility_id": utility_id,
            "revision_number": row.revision_number,
            "basis": row.basis,
        },
    )
    return _rule_out(row)


@router.post("/{property_id}/rubs/utilities/{utility_id}/allocation-preview")
def preview_allocation(
    property_id: int,
    utility_id: int,
    payload: AllocationPreviewRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _rubs_property(db, current_user, property_id)
    _shared_utility(db, property_id=prop.id, utility_id=utility_id)
    rule = (
        db.query(UtilityAllocationRuleRevision)
        .filter(
            UtilityAllocationRuleRevision.id == payload.rule_revision_id,
            UtilityAllocationRuleRevision.utility_id == utility_id,
        )
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Allocation-rule revision not found.")
    if not rule.is_authorized or rule.status != "AUTHORIZED":
        raise HTTPException(
            status_code=409,
            detail="Allocation-rule revision requires explicit authorization before preview.",
        )

    bill = (
        db.query(UtilityBill)
        .filter(UtilityBill.id == payload.bill_id, UtilityBill.utility_id == utility_id)
        .first()
    )
    if bill is None:
        raise HTTPException(status_code=404, detail="Utility bill not found.")
    if (
        bill.billing_period_start is None
        or bill.billing_period_end is None
        or bill.billing_period_start > bill.billing_period_end
    ):
        raise HTTPException(
            status_code=422,
            detail="Selected utility bill requires one complete valid billing period.",
        )
    if rule.effective_date > bill.billing_period_start:
        raise HTTPException(
            status_code=422,
            detail="Rule revision is not yet effective for the selected bill period.",
        )

    other_bills = (
        db.query(UtilityBill)
        .filter(UtilityBill.utility_id == utility_id, UtilityBill.id != bill.id)
        .limit(MAX_PREVIEW_BILLS + 1)
        .all()
    )
    if len(other_bills) > MAX_PREVIEW_BILLS:
        raise HTTPException(status_code=422, detail="Too many utility bills for RUBs preview.")
    for other in other_bills:
        if (
            other.billing_period_start is not None
            and other.billing_period_end is not None
            and other.billing_period_start <= other.billing_period_end
            and other.billing_period_start <= bill.billing_period_end
            and other.billing_period_end >= bill.billing_period_start
        ):
            raise HTTPException(
                status_code=422,
                detail="Selected utility bill overlaps another recorded bill period.",
            )

    inputs = json.loads(rule.unit_inputs_json)
    unit_ids = [int(item["unit_id"]) for item in inputs]
    _allocation_units(db, property_id=prop.id, unit_ids=unit_ids)
    ordered = sorted(
        (
            {"unit_id": int(item["unit_id"]), "weight": Decimal(str(item["weight"]))}
            for item in inputs
        ),
        key=lambda item: item["unit_id"],
    )
    total_weight = sum((item["weight"] for item in ordered), Decimal("0"))
    if total_weight <= 0:
        raise HTTPException(status_code=422, detail="Allocation rule has no positive weight.")

    amount = Decimal(bill.amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Selected utility bill must be positive.")
    details = []
    allocated = Decimal("0")
    for item in ordered:
        exact = amount * item["weight"] / total_weight
        rounded = exact.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        allocated += rounded
        details.append(
            {
                "unit_id": item["unit_id"],
                "weight": item["weight"],
                "share": item["weight"] / total_weight,
                "amount": rounded,
            }
        )
    remainder_cents = int(((amount - allocated) * 100).to_integral_value())
    for index in range(remainder_cents):
        details[index % len(details)]["amount"] += Decimal("0.01")

    response.headers["Cache-Control"] = "no-store"
    return {
        "property_id": prop.id,
        "utility_id": utility_id,
        "bill_id": bill.id,
        "billing_period_start": bill.billing_period_start,
        "billing_period_end": bill.billing_period_end,
        "bill_amount": amount,
        "rule_revision_id": rule.id,
        "rule_revision_number": rule.revision_number,
        "basis": rule.basis,
        "items": details,
        "allocated_total": sum((item["amount"] for item in details), Decimal("0")),
        "remainder_rule": (
            "Round each raw unit share down to cents, then distribute remaining "
            "cents by ascending unit ID."
        ),
        "posting_created": False,
        "tenant_charge_created": False,
        "owner_charge_created": False,
        "gl_created": False,
        "meaning": (
            "Finance-neutral preview only. Explicit unit selection and weights do not "
            "establish legal eligibility or a tenant/owner payment obligation."
        ),
    }
