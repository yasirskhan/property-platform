"""Active property directory: recorded addresses and configured unit inventory.

Never infer tenancy, occupancy, collected rent, owners or geographic identity
from property metadata. Only explicitly authorized live properties are listed.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import User
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param


HEADERS = (
    "Property ID", "Property Name", "Property Type",
    "Address Line 1", "Address Line 2", "City", "State",
    "Postal Code", "Country", "Active Unit Records",
    "Year Built (recorded)", "Square Feet (recorded)",
)


def _role(user: User) -> str:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return str(role or "").upper()


def build_property_directory(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id", "property_type"}:
        raise ReportDeliveryError("Unsupported property directory parameter")
    requested_id = _int_param(parameters, "property_id")
    raw_type = str(parameters.get("property_type") or "").strip().lower()
    if raw_type and raw_type not in {option.value for option in PropertyType}:
        raise ReportDeliveryError("Unsupported property type")

    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Property directory permission required")
    for menu in ("REPORTING.ALL", "PROPERTIES.ALL"):
        if not permission_allows_user(db, user=current_user, menu_key=menu):
            raise ReportDeliveryError("Property directory permission required")

    properties = db.query(Property).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if role == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        properties = properties.filter(Property.id.in_(assigned))
    if requested_id is not None:
        properties = properties.filter(Property.id == requested_id)
        if properties.first() is None:
            raise ReportDeliveryError("Property not found")
    if raw_type:
        properties = properties.filter(Property.property_type == PropertyType(raw_type))
    records = properties.order_by(Property.name.asc(), Property.id.asc()).all()

    ids = [prop.id for prop in records]
    counts: dict[int, int] = {}
    if ids:
        counts = {
            prop_id: int(count)
            for prop_id, count in db.query(
                Unit.property_id, func.count(Unit.id),
            ).filter(
                Unit.property_id.in_(ids),
                Unit.is_active.is_(True),
                Unit.deleted_at.is_(None),
            ).group_by(Unit.property_id).all()
        }
    rows = tuple(
        (
            prop.id, prop.name, prop.property_type.value,
            prop.address_line1, prop.address_line2 or "",
            prop.city, prop.state, prop.zip_code, prop.country or "",
            counts.get(prop.id, 0),
            prop.year_built if prop.year_built is not None else "",
            prop.square_feet if prop.square_feet is not None else "",
        )
        for prop in records
    )
    return ReportPayload(
        title="Active property directory (recorded property and unit data only)",
        filename="property-directory.csv", headers=HEADERS, rows=rows,
    )
