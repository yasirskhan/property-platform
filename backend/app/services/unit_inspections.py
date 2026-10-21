"""Scoped, immutable manually recorded inspections and read-only report.

These records do not substitute for Phase 5 mobile/offline/photo/checklist
inspections. No inspection is fabricated from WorkOrder or Unit flags.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment, Unit
from app.models.unit_inspection import UnitInspectionRecord
from app.models.user import User, UserRole
from app.schemas.unit_inspection import InspectionChecklistItem, UnitInspectionCreateIn, UnitInspectionOut
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param, _int_param

HEADERS = (
    "Property", "Unit", "Inspection Date (staff-recorded)",
    "Condition (staff-recorded)", "Findings (staff-recorded)",
    "Checklist (staff-recorded)",
    "Recorded By User ID", "Recorded At", "Inspection Record ID",
    "Property ID", "Unit ID",
)


def _role(actor: User) -> str:
    val = actor.role.value if hasattr(actor.role, "value") else actor.role
    return str(val or "").upper()


def _visible_properties(
    db: Session, *, organization_id: int, actor: User,
    include_inactive: bool = False,
):
    if (actor.organization_id != organization_id or not actor.is_active
            or actor.deleted_at is not None
            or _role(actor) not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Unit inspection permission required")
    for key in ("REPORTING.ALL", "PROPERTIES.ALL", "PROPERTIES.UNITS"):
        if not permission_allows_user(db, user=actor, menu_key=key):
            raise ReportDeliveryError("Unit inspection permission required")
    query = db.query(Property).filter(
        Property.organization_id == organization_id,
    )
    # Recording requires active inventory; historical inspection review must
    # not lose records when a property is later retired or soft-deleted.
    if not include_inactive:
        query = query.filter(
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
    if _role(actor) == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.role == UserRole.MANAGER,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    return query


def _scope(
    db: Session, *, organization_id: int, actor: User,
    property_id: int | None = None, unit_id: int | None = None,
    include_inactive: bool = False,
):
    query = _visible_properties(
        db, organization_id=organization_id, actor=actor,
        include_inactive=include_inactive,
    )
    if property_id is not None:
        query = query.filter(Property.id == property_id)
        if query.first() is None:
            raise ReportDeliveryError("Property not found")
    by_property = {prop.id: prop for prop in query.all()}
    units = db.query(Unit).filter(Unit.property_id.in_(list(by_property)))
    if not include_inactive:
        units = units.filter(
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        )
    if unit_id is not None:
        units = units.filter(Unit.id == unit_id)
        if units.first() is None:
            raise ReportDeliveryError("Unit not found")
    return by_property, {unit.id: unit for unit in units.all()}



def _same_org_recorder_labels(db: Session, organization_id: int, ids: set[int]) -> dict[int, str]:
    """Resolve only visible organization's actors, in one bounded query."""
    if not ids:
        return {}
    rows = db.query(User).filter(
        User.organization_id == organization_id, User.id.in_(ids),
    ).all()
    return {
        row.id: " ".join(part for part in (row.first_name, row.last_name) if part).strip()
        for row in rows
    }


def record_inspection(
    db: Session, *, actor: User, payload: UnitInspectionCreateIn,
) -> UnitInspectionOut:
    org_id = actor.organization_id
    if org_id is None:
        raise ReportDeliveryError("Unit inspection permission required")
    properties, units = _scope(
        db, organization_id=org_id, actor=actor, unit_id=payload.unit_id,
    )
    unit = units[payload.unit_id]
    if unit.property_id not in properties:
        raise ReportDeliveryError("Unit not found")
    row = UnitInspectionRecord(
        organization_id=org_id, property_id=unit.property_id, unit_id=unit.id,
        inspection_date=payload.inspection_date,
        recorded_condition=payload.recorded_condition,
        findings=payload.findings,
        checklist_json=json.dumps([item.model_dump() for item in payload.checklist_items]) if payload.checklist_items else None,
        recorded_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=actor.id,
        entity_type="unit_inspection_record", entity_id=row.id,
        action="created",
        new_value={
            "property_id": row.property_id, "unit_id": row.unit_id,
            "inspection_date": row.inspection_date.isoformat(),
            "recorded_condition": row.recorded_condition,
            "findings": row.findings,
            "checklist_items": [item.model_dump() for item in payload.checklist_items],
        },
    )
    db.commit()
    db.refresh(row)
    return UnitInspectionOut.model_validate(row).model_copy(update={
        "property_name": properties[unit.property_id].name,
        "unit_number": unit.unit_number,
        "recorded_by_name": " ".join(part for part in (actor.first_name, actor.last_name) if part).strip() or None,
        "checklist_items": payload.checklist_items,
    })


def list_inspections(
    db: Session, *, actor: User, property_id: int | None = None,
    unit_id: int | None = None, limit: int | None = None, offset: int = 0,
    recorded_condition: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
) -> list[UnitInspectionOut]:
    org_id = actor.organization_id
    if org_id is None:
        raise ReportDeliveryError("Unit inspection permission required")
    properties, units = _scope(
        db, organization_id=org_id, actor=actor,
        property_id=property_id, unit_id=unit_id,
        include_inactive=True,
    )
    if not units:
        return []
    query = db.query(UnitInspectionRecord).join(
        Unit, Unit.id == UnitInspectionRecord.unit_id,
    ).filter(
        UnitInspectionRecord.organization_id == org_id,
        UnitInspectionRecord.unit_id.in_(list(units)),
        # Malformed historical rows must not reinterpret unit/property scope.
        # The stored parent must agree with the actual Unit -> Property link.
        UnitInspectionRecord.property_id == Unit.property_id,
    ).order_by(
        UnitInspectionRecord.inspection_date.desc(),
        UnitInspectionRecord.id.desc(),
    )
    if recorded_condition is not None:
        query = query.filter(UnitInspectionRecord.recorded_condition == recorded_condition)
    if date_from is not None:
        query = query.filter(UnitInspectionRecord.inspection_date >= date_from)
    if date_to is not None:
        query = query.filter(UnitInspectionRecord.inspection_date <= date_to)
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    # Resolve labels solely from already authorized unit/property objects,
    # including retired inventory, without a second unscoped lookup.
    rows = query.all()
    labels = _same_org_recorder_labels(db, org_id, {
        row.recorded_by_id for row in rows if row.recorded_by_id is not None
    })
    return [
        UnitInspectionOut.model_validate(row).model_copy(update={
            "recorded_by_name": labels.get(row.recorded_by_id),
            "property_name": properties[units[row.unit_id].property_id].name,
            "unit_number": units[row.unit_id].unit_number,
            "checklist_items": [
                InspectionChecklistItem.model_validate(item)
                for item in json.loads(row.checklist_json or "[]")
            ],
        })
        for row in rows
    ]



def get_inspection(
    db: Session, *, actor: User, inspection_id: int,
) -> UnitInspectionOut:
    """Return one immutable inspection only through its actual scoped unit."""
    org_id = actor.organization_id
    if org_id is None:
        raise ReportDeliveryError("Unit inspection permission required")
    # Role and menu authorization must be applied even when the ID is unknown.
    visible = _visible_properties(
        db, organization_id=org_id, actor=actor, include_inactive=True,
    )
    row = db.query(UnitInspectionRecord).join(
        Unit, Unit.id == UnitInspectionRecord.unit_id,
    ).filter(
        UnitInspectionRecord.id == inspection_id,
        UnitInspectionRecord.organization_id == org_id,
        UnitInspectionRecord.property_id == Unit.property_id,
        Unit.property_id.in_(visible.with_entities(Property.id)),
    ).first()
    if row is None:
        raise ReportDeliveryError("Unit inspection not found")
    # Inventory labels are resolved only after the above scope check.
    unit = db.query(Unit).filter(
        Unit.id == row.unit_id, Unit.property_id == row.property_id,
    ).one()
    prop = db.query(Property).filter(
        Property.id == row.property_id,
        Property.organization_id == org_id,
    ).one()
    return UnitInspectionOut.model_validate(row).model_copy(update={
        "property_name": prop.name,
        "unit_number": unit.unit_number,
        "recorded_by_name": _same_org_recorder_labels(
            db, org_id, {row.recorded_by_id} if row.recorded_by_id is not None else set(),
        ).get(row.recorded_by_id),
        "checklist_items": [
            InspectionChecklistItem.model_validate(item)
            for item in json.loads(row.checklist_json or "[]")
        ],
    })


def build_inspection_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id", "unit_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported inspection parameter")
    requested_property = _int_param(parameters, "property_id")
    requested_unit = _int_param(parameters, "unit_id")
    from_date = _date_param(parameters, "date_from")
    to_date = _date_param(parameters, "date_to")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ReportDeliveryError("date_from cannot be after date_to")
    properties, units = _scope(
        db, organization_id=organization_id, actor=current_user,
        property_id=requested_property, unit_id=requested_unit,
        include_inactive=True,
    )
    if not units:
        return ReportPayload(
            title="Staff-recorded unit inspection entries (no inferred inspections)",
            filename="unit-inspections-recorded.csv", headers=HEADERS, rows=(),
        )
    query = db.query(UnitInspectionRecord).join(
        Unit, Unit.id == UnitInspectionRecord.unit_id,
    ).filter(
        UnitInspectionRecord.organization_id == organization_id,
        UnitInspectionRecord.unit_id.in_(list(units)),
        # Malformed historical rows must not reinterpret unit/property scope.
        # The stored parent must agree with the actual Unit -> Property link.
        UnitInspectionRecord.property_id == Unit.property_id,
    )
    if from_date is not None:
        query = query.filter(UnitInspectionRecord.inspection_date >= from_date)
    if to_date is not None:
        query = query.filter(UnitInspectionRecord.inspection_date <= to_date)
    records = query.order_by(
        UnitInspectionRecord.inspection_date.desc(),
        UnitInspectionRecord.id.desc(),
    ).all()
    rows = tuple((
        properties[record.property_id].name,
        units[record.unit_id].unit_number,
        record.inspection_date,
        record.recorded_condition,
        record.findings,
        record.checklist_json or "",
        record.recorded_by_id if record.recorded_by_id is not None else "",
        record.recorded_at,
        record.id, record.property_id, record.unit_id,
    ) for record in records)
    return ReportPayload(
        title="Staff-recorded unit inspections (not Phase 5 verified mobile inspections)",
        filename="unit-inspections-recorded.csv",
        headers=HEADERS, rows=rows,
    )
