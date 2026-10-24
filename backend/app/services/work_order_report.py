"""Read-only current recorded work order register, respecting existing staff scope.

Do NOT expose entry notes, occupant identifiers, photo URLs, private work
history or estimated/unposted expenses through the generic report export.
"""
from __future__ import annotations

from datetime import date
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)

HEADERS = (
    "Recorded Created At", "Work Order ID", "Property ID", "Property",
    "Unit", "Recorded Title", "Category", "Priority", "Status",
    "Recorded Completed At", "Recorded Total Cost",
)


def build_work_order_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id", "date_from", "date_to", "status"}:
        raise ReportDeliveryError("Unsupported work order parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
    ):
        raise ReportDeliveryError("Work order report permission required")
    for key in ("REPORTING.ALL", "MAINTENANCE.WORK_ORDERS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Work order report permission required")
    property_id = _int_param(parameters, "property_id")
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    status_value = parameters.get("status")
    selected_status = None
    if status_value not in (None, ""):
        try:
            selected_status = WorkOrderStatus(str(status_value).lower())
        except ValueError as exc:
            raise ReportDeliveryError("Invalid work order status") from exc

    permitted = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if current_user.role == UserRole.MANAGER:
        permitted = permitted.join(
            PropertyAssignment, PropertyAssignment.property_id == Property.id,
        ).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
    if property_id is not None:
        permitted = permitted.filter(Property.id == property_id)
        if permitted.first() is None:
            raise ReportDeliveryError("Property not found")

    query = db.query(WorkOrder, Property, Unit).join(
        Property, Property.id == WorkOrder.property_id,
    ).join(
        Unit, Unit.id == WorkOrder.unit_id,
    ).filter(
        Property.id.in_(permitted),
        Unit.property_id == Property.id,
        Unit.is_active.is_(True),
        Unit.deleted_at.is_(None),
    )
    if date_from is not None:
        query = query.filter(WorkOrder.created_at >= date_from)
    if date_to is not None:
        from datetime import datetime, time, timedelta
        query = query.filter(
            WorkOrder.created_at < datetime.combine(date_to + timedelta(days=1), time.min),
        )
    if selected_status is not None:
        query = query.filter(WorkOrder.status == selected_status)
    rows = tuple(
        (
            work.created_at, work.id, prop.id, prop.name,
            unit.unit_number, work.title,
            work.category.value, work.priority.value, work.status.value,
            work.completed_at or "", work.total_cost if work.total_cost is not None else "",
        )
        for work, prop, unit in query.order_by(
            WorkOrder.created_at.asc(), WorkOrder.id.asc(),
        ).all()
    )
    return ReportPayload(
        title="Recorded work order summary (private entry instructions excluded)",
        filename="work-order-summary.csv", headers=HEADERS, rows=rows,
    )
