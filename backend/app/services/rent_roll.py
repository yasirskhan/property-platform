"""Current-config unit rent roll from actual lease records, never cash receipts.

A historical date cannot be reconstructed from current editable leases. Always
use current recorded eligibility and disclose that no eligible lease does NOT
prove physical vacancy. Conflicting active leases fail closed.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param


HEADERS = (
    "Property", "Unit", "Recorded Lease Association",
    "Current Config Market Rent", "Current Contract Rent",
    "Tenant", "Lease Start", "Lease End", "Lease ID",
    "Property ID", "Unit ID", "Tenant ID",
)


def _role(user: User) -> str:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return str(role or "").upper()


def build_rent_roll(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported rent roll parameter")
    requested = _int_param(parameters, "property_id")
    if (current_user.organization_id != organization_id or
            not current_user.is_active or current_user.deleted_at is not None or
            _role(current_user) not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Rent roll permission required")
    for key in ("REPORTING.ALL", "PROPERTIES.ALL", "LEASING"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Rent roll permission required")

    visible = db.query(Property).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
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
    ids = [prop.id for prop in properties]
    units = (
        db.query(Unit).filter(
            Unit.property_id.in_(ids),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        ).order_by(Unit.property_id.asc(), Unit.unit_number.asc(), Unit.id.asc()).all()
        if ids else []
    )
    now = date.today()
    unit_ids = [unit.id for unit in units]
    leases = (
        db.query(Lease).filter(
            Lease.unit_id.in_(unit_ids),
            Lease.status == LeaseStatus.ACTIVE,
            Lease.start_date <= now,
            Lease.end_date >= now,
        ).order_by(Lease.id.asc()).all()
        if unit_ids else []
    )
    lease_by_unit: dict[int, Lease] = {}
    for lease in leases:
        if lease.unit_id in lease_by_unit:
            # Even leases of the same tenant cannot be silently merged.
            raise ReportDeliveryError("Overlapping active leases require review")
        lease_by_unit[lease.unit_id] = lease

    tenant_ids = {lease.tenant_id for lease in leases}
    tenants = {
        user.id: user for user in db.query(User).filter(
            User.id.in_(tenant_ids),
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        ).all()
    } if tenant_ids else {}
    if set(tenants) != tenant_ids:
        # Don't silently present malformed cross-org tenant links as vacancy.
        raise ReportDeliveryError("Current lease tenant scope is invalid")

    by_property = {prop.id: prop for prop in properties}
    rows = []
    for unit in units:
        prop = by_property[unit.property_id]
        lease = lease_by_unit.get(unit.id)
        tenant = tenants[lease.tenant_id] if lease is not None else None
        rows.append((
            prop.name, unit.unit_number,
            "CURRENT RECORDED LEASE" if lease is not None else
            "NO ELIGIBLE CURRENT LEASE (vacancy not verified)",
            Decimal(unit.monthly_rent or 0),
            Decimal(lease.monthly_rent) if lease is not None else "",
            f"{tenant.first_name} {tenant.last_name}".strip() if tenant else "",
            lease.start_date if lease else "",
            lease.end_date if lease else "",
            lease.id if lease else "",
            prop.id, unit.id, tenant.id if tenant else "",
        ))
    return ReportPayload(
        title=f"Current-config rent roll as of {now.isoformat()} (not historical occupancy or cash)",
        filename=f"rent-roll-current-records-{now.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
