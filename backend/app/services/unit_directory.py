"""Current configured unit inventory, not physical vacancy or lease occupancy.

Read-only, organization and manager-assignment scoped.  The editable Unit
is_available and is_listed flags are displayed as *recorded settings*, never
substituted for a verified lease or visit.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param


HEADERS = (
    "Property", "Unit", "Bedrooms (recorded)", "Bathrooms (recorded)",
    "Square Feet (recorded)", "Configured Monthly Rent",
    "Configured Security Deposit", "Configured Pet Deposit",
    "Configured Pet Rent", "Available Flag (recorded, not vacancy)",
    "Listed Flag (recorded)", "Available From (recorded)",
    "Property ID", "Unit ID",
)


def _role(user: User) -> str:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return str(role or "").upper()


def build_unit_directory(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported unit directory parameter")
    requested = _int_param(parameters, "property_id")
    if (current_user.organization_id != organization_id or
            not current_user.is_active or current_user.deleted_at is not None or
            _role(current_user) not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Unit directory permission required")
    for key in ("REPORTING.ALL", "PROPERTIES.ALL", "PROPERTIES.UNITS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Unit directory permission required")
    visible = db.query(Property).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    )
    if _role(current_user) == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        visible = visible.filter(Property.id.in_(assigned))
    if requested is not None:
        visible = visible.filter(Property.id == requested)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")
    properties = visible.order_by(Property.name.asc(), Property.id.asc()).all()
    by_id = {prop.id: prop for prop in properties}
    units = db.query(Unit).filter(
        Unit.property_id.in_(list(by_id)),
        Unit.is_active.is_(True),
        Unit.deleted_at.is_(None),
    ).order_by(Unit.property_id.asc(), Unit.unit_number.asc(), Unit.id.asc()).all() if by_id else []
    rows = tuple((
        by_id[unit.property_id].name,
        unit.unit_number,
        unit.bedrooms,
        unit.bathrooms,
        unit.square_feet if unit.square_feet is not None else "",
        unit.monthly_rent,
        unit.security_deposit if unit.security_deposit is not None else "",
        unit.pet_deposit if unit.pet_deposit is not None else "",
        unit.pet_rent if unit.pet_rent is not None else "",
        "YES" if unit.is_available else "NO",
        "YES" if unit.is_listed else "NO",
        unit.available_from if unit.available_from is not None else "",
        unit.property_id, unit.id,
    ) for unit in units)
    return ReportPayload(
        title="Current recorded unit directory (availability and listing flags are not verified occupancy)",
        filename="unit-directory-current-configuration.csv",
        headers=HEADERS, rows=rows,
    )
