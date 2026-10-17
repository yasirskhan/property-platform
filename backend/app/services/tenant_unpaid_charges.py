"""Current unpaid standalone charges; NOT rent invoices or reconciled GL balances.

Charge.amount_paid is a current recorded snapshot. A separate invoice may
include a late fee, so never sum RentInvoice here and claim a unified total.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param

HEADERS = (
    "Charge Date", "Tenant", "Property", "Unit", "Charge ID",
    "Description", "Charge Amount", "Recorded Paid", "Outstanding",
    "Tenant ID", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def build_tenant_unpaid_charges(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Unpaid tenant charges are not available to this user")
    if not permission_allows_user(db, user=current_user, menu_key="LEASING"):
        raise ReportDeliveryError("Tenant report permission required")
    if not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.CHARGES"):
        raise ReportDeliveryError("Tenant charge permission required")
    if set(parameters) - {"tenant_id", "property_id"}:
        raise ReportDeliveryError("Unsupported unpaid charge parameter")
    tenant_id = _int_param(parameters, "tenant_id")
    property_id = _int_param(parameters, "property_id")

    tenant_query = db.query(User).filter(
        User.organization_id == organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if tenant_id is not None and tenant_query.filter(User.id == tenant_id).first() is None:
        raise ReportDeliveryError("Tenant not found")

    visible = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if role == "MANAGER":
        assignment = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        visible = visible.filter(Property.id.in_(assignment))
    if property_id is not None:
        visible = visible.filter(Property.id == property_id)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")

    # A propertyless standalone charge is visible only to org ADMIN.
    # Do not connect unrelated units/properties or leak other-org names.
    query = (
        db.query(Charge, User, Property, Unit)
        .join(User, User.id == Charge.tenant_user_id)
        .outerjoin(Property, and_(
            Property.id == Charge.property_id,
            Property.organization_id == organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        ))
        .outerjoin(Unit, and_(
            Unit.id == Charge.unit_id,
            Unit.property_id == Charge.property_id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        ))
        .filter(
            Charge.organization_id == organization_id,
            Charge.is_active.is_(True),
            Charge.deleted_at.is_(None),
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            # Do not surface a foreign/deleted/inactive property ID as
            # an apparently unallocated charge.
            or_(Charge.property_id.is_(None), Property.id.in_(visible)),
        )
    )
    if role == "MANAGER" or property_id is not None:
        query = query.filter(Charge.property_id.in_(visible))
    if tenant_id is not None:
        query = query.filter(User.id == tenant_id)

    rows: list[tuple[object, ...]] = []
    for charge, tenant, prop, unit in query.all():
        billed = Decimal(charge.amount or 0)
        paid = Decimal(charge.amount_paid or 0)
        outstanding = billed - paid
        if outstanding <= 0:
            continue
        rows.append((
            charge.charge_date, f"{tenant.first_name} {tenant.last_name}".strip(),
            prop.name if prop is not None else "Unallocated organization charge",
            unit.unit_number if unit is not None else "",
            charge.id, charge.description, billed, paid, outstanding,
            tenant.id, prop.id if prop is not None else "",
        ))
    rows.sort(key=lambda row: (row[0], int(row[9]), int(row[4])))
    if role == "MANAGER" and tenant_id is not None and not rows:
        # No confirmation that the tenant exists outside assigned scope.
        raise ReportDeliveryError("Tenant not found")
    return ReportPayload(
        title=f"Unpaid standalone tenant charges as of {date.today().isoformat()}",
        filename=f"tenant-unpaid-charges-{date.today().isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
