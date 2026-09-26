"""Current tenant directory scoped through live leases and property assignments.

Admin sees all active tenant users (including those without any eligible
current lease). Managers see only tenants on their assigned current leases.
No historical lease or other-org contact information is disclosed.
"""
from __future__ import annotations

from datetime import date
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param


HEADERS = (
    "Tenant ID", "Tenant", "Email", "Phone", "Property", "Unit",
    "Lease ID", "Lease Start", "Lease End", "Association", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def build_tenant_directory(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Tenant directory is not available to this user")
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported tenant directory parameter")
    property_id = _int_param(parameters, "property_id")

    visible = db.query(Property.id).filter(
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
        visible = visible.filter(Property.id.in_(assigned))
    if property_id is not None:
        visible = visible.filter(Property.id == property_id)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")

    today = date.today()
    associations = (
        db.query(User, Lease, Unit, Property)
        .join(Lease, Lease.tenant_id == User.id)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Property.id.in_(visible),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
            Lease.status == LeaseStatus.ACTIVE,
            Lease.start_date <= today,
            Lease.end_date >= today,
        )
        .order_by(User.last_name.asc(), User.first_name.asc(),
                  User.id.asc(), Lease.id.asc())
    )
    rows: list[tuple[object, ...]] = []
    included: set[int] = set()
    for tenant, lease, unit, prop in associations.all():
        included.add(tenant.id)
        rows.append((
            tenant.id, f"{tenant.first_name} {tenant.last_name}".strip(),
            tenant.email, tenant.phone or "", prop.name, unit.unit_number,
            lease.id, lease.start_date, lease.end_date, "Current lease", prop.id,
        ))

    if role == "ADMIN" and property_id is None:
        # Only admin sees unassigned tenants, and only from its own org.
        # A previous or inaccessible lease is NOT shown or claimed current.
        unassigned = (
            db.query(User)
            .filter(
                User.organization_id == organization_id,
                User.role == UserRole.TENANT,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
        )
        for tenant in unassigned.all():
            if tenant.id in included:
                continue
            rows.append((
                tenant.id, f"{tenant.first_name} {tenant.last_name}".strip(),
                tenant.email, tenant.phone or "",
                "", "", "", "", "", "No eligible current lease", "",
            ))
    rows.sort(key=lambda row: (str(row[1]).casefold(), int(row[0]),
                               int(row[6]) if row[6] != "" else 0))
    return ReportPayload(
        title=f"Tenant directory as of {today.isoformat()}",
        filename=f"tenant-directory-{today.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
