"""Scoped, immutable manually recorded inspections and read-only report.

These records do not substitute for Phase 5 mobile/offline/photo/checklist
inspections. No inspection is fabricated from WorkOrder or Unit flags.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment, Unit
from app.models.unit_inspection import UnitInspectionRecord
from app.models.user import User
from app.schemas.unit_inspection import UnitInspectionCreateIn, UnitInspectionOut
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param, _int_param

HEADERS = (
    "Property", "Unit", "Inspection Date (staff-recorded)",
    "Condition (staff-recorded)", "Findings (staff-recorded)",
    "Recorded By User ID", "Recorded At", "Inspection Record ID",
    "Property ID", "Unit ID",
)


def _role(actor: User) -> str:
    val = actor.role.value if hasattr(actor.role, "value") else actor.role
    return str(val or "").upper()


def _visible_properties(db: Session, *, organization_id: int, actor: User):
    if (actor.organization_id != organization_id or not actor.is_active
            or actor.deleted_at is not None
            or _role(actor) not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Unit inspection permission required")
    for key in ("REPORTING.ALL", "PROPERTIES.ALL", "PROPERTIES.UNITS"):
        if not permission_allows_user(db, user=actor, menu_key=key):
            raise ReportDeliveryError("Unit inspection permission required")
    query = db.query(Property).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if _role(actor) == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    return query


def _scope(
    db: Session, *, organization_id: int, actor: User,
    property_id: int | None = None, unit_id: int | None = None,
):
    query = _visible_properties(db, organization_id=organization_id, actor=actor)
    if property_id is not None:
        query = query.filter(Property.id == property_id)
        if query.first() is None:
            raise ReportDeliveryError("Property not found")
    by_property = {prop.id: prop for prop in query.all()}
    units = db.query(Unit).filter(
        Unit.property_id.in_(list(by_property)),
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
    )
    if unit_id is not None:
        units = units.filter(Unit.id == unit_id)
        if units.first() is None:
            raise ReportDeliveryError("Unit not found")
    return by_property, {unit.id: unit for unit in units.all()}


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
        },
    )
    db.commit()
    db.refresh(row)
    return UnitInspectionOut.model_validate(row)


def list_inspections(
    db: Session, *, actor: User, property_id: int | None = None,
    unit_id: int | None = None,
) -> list[UnitInspectionOut]:
    org_id = actor.organization_id
    if org_id is None:
        raise ReportDeliveryError("Unit inspection permission required")
    _, units = _scope(
        db, organization_id=org_id, actor=actor,
        property_id=property_id, unit_id=unit_id,
    )
    if not units:
        return []
    rows = db.query(UnitInspectionRecord).filter(
        UnitInspectionRecord.organization_id == org_id,
        UnitInspectionRecord.unit_id.in_(list(units)),
    ).order_by(
        UnitInspectionRecord.inspection_date.desc(),
        UnitInspectionRecord.id.desc(),
    ).all()
    return [UnitInspectionOut.model_validate(row) for row in rows]


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
    )
    if not units:
        return ReportPayload(
            title="Staff-recorded unit inspection entries (no inferred inspections)",
            filename="unit-inspections-recorded.csv", headers=HEADERS, rows=(),
        )
    query = db.query(UnitInspectionRecord).filter(
        UnitInspectionRecord.organization_id == organization_id,
        UnitInspectionRecord.unit_id.in_(list(units)),
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
        record.recorded_by_id if record.recorded_by_id is not None else "",
        record.recorded_at,
        record.id, record.property_id, record.unit_id,
    ) for record in records)
    return ReportPayload(
        title="Staff-recorded unit inspections (not Phase 5 verified mobile inspections)",
        filename="unit-inspections-recorded.csv",
        headers=HEADERS, rows=rows,
    )
