"""Organization-scoped mailing labels sourced from existing property and lease records.

Rows are suitable as CSV mail-merge input. No contact addresses are invented:
tenant labels use the current property's recorded physical address.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param


HEADERS = (
    "RecipientName", "AddressLine1", "AddressLine2", "City",
    "State", "PostalCode", "Country", "RecipientType",
    "RecipientId", "PropertyId",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def _property_scope(query, *, user: User, role: str):
    if role == "MANAGER":
        return query.join(
            PropertyAssignment, PropertyAssignment.property_id == Property.id,
        ).filter(
            PropertyAssignment.user_id == user.id,
            PropertyAssignment.is_active.is_(True),
        )
    return query


def build_label_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    """Fail closed on tenant access, unknown parameters and out-of-scope records."""
    role = _role(current_user)
    if current_user.organization_id != organization_id or role not in {"ADMIN", "OWNER", "MANAGER"}:
        raise ReportDeliveryError("Label report is not available to this user")
    if set(parameters) - {"recipient_type", "property_id"}:
        raise ReportDeliveryError("Unsupported label parameter")
    recipient_type = str(parameters.get("recipient_type") or "PROPERTY").strip().upper()
    if recipient_type not in {"PROPERTY", "TENANT"}:
        raise ReportDeliveryError("recipient_type must be PROPERTY or TENANT")
    property_id = _int_param(parameters, "property_id")

    base = db.query(Property).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
    )
    base = _property_scope(base, user=current_user, role=role)
    if property_id is not None:
        # Unknown, deleted and unauthorized property IDs are indistinguishable.
        if base.filter(Property.id == property_id).first() is None:
            raise ReportDeliveryError("Property not found")
        base = base.filter(Property.id == property_id)

    if recipient_type == "PROPERTY":
        rows = tuple(
            (
                prop.name, prop.address_line1, prop.address_line2 or "",
                prop.city, prop.state, prop.zip_code, prop.country or "",
                "PROPERTY", prop.id, prop.id,
            )
            for prop in base.order_by(Property.name.asc(), Property.id.asc()).all()
        )
        return ReportPayload(
            title="Property mailing labels", filename="property-mail-merge.csv",
            headers=HEADERS, rows=rows,
        )

    if not permission_allows_user(db, user=current_user, menu_key="LEASING"):
        raise ReportDeliveryError("Lease permission required for tenant labels")

    # A label belongs to an active tenant's active lease, not to any
    # unrelated organization user or historical/terminated tenancy.
    # The property query above is the authoritative staff visibility scope.
    query = (
        db.query(Lease, Unit, Property, User)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .join(User, User.id == Lease.tenant_id)
        .filter(
            Property.id.in_(base.with_entities(Property.id)),
            Unit.is_active.is_(True),
            Lease.status == LeaseStatus.ACTIVE,
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
        )
    )
    rows = []
    for lease, unit, prop, tenant in query.order_by(
        Property.name.asc(), Unit.unit_number.asc(), Lease.id.asc(),
    ).all():
        second_line = prop.address_line2 or ""
        unit_label = f"Unit {unit.unit_number.strip()}" if unit.unit_number and unit.unit_number.strip() else ""
        if unit_label and unit_label.lower() not in second_line.lower():
            second_line = ", ".join(part for part in (second_line, unit_label) if part)
        rows.append((
            f"{tenant.first_name} {tenant.last_name}".strip(),
            prop.address_line1, second_line, prop.city, prop.state,
            prop.zip_code, prop.country or "", "TENANT", tenant.id, prop.id,
        ))
    return ReportPayload(
        title="Current-tenant mailing labels", filename="tenant-mail-merge.csv",
        headers=HEADERS, rows=tuple(rows),
    )
