"""Current overdue rent invoices; never infer an historical AR snapshot from live payments."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.lease import InvoiceStatus, Lease, RentInvoice
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param

HEADERS = (
    "Tenant", "Property", "Unit", "Invoice ID", "Due Date",
    "Days Overdue", "Rent Due", "Late Fee", "Paid",
    "Outstanding", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def build_delinquency_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    """Uses already-recorded invoice balances; no GL re-posting or guessed charges."""
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Delinquency report is not available to this user")
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported delinquency parameter")
    property_id = _int_param(parameters, "property_id")
    visible = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if role == "MANAGER":
        allowed = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        visible = visible.filter(Property.id.in_(allowed))
    if property_id is not None:
        visible = visible.filter(Property.id == property_id)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")

    today = date.today()
    invoices = (
        db.query(RentInvoice, Unit, Property, User)
        .join(Lease, Lease.id == RentInvoice.lease_id)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .join(User, User.id == Lease.tenant_id)
        .filter(
            Property.id.in_(visible),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            RentInvoice.due_date < today,
            RentInvoice.status != InvoiceStatus.VOID,
        )
        .order_by(RentInvoice.due_date.asc(), Property.id.asc(), RentInvoice.id.asc())
    )
    rows: list[tuple[object, ...]] = []
    for invoice, unit, prop, tenant in invoices.all():
        rent = Decimal(invoice.amount_due or 0)
        late_fee = Decimal(invoice.late_fee or 0)
        paid = Decimal(invoice.amount_paid or 0)
        outstanding = rent + late_fee - paid
        if outstanding <= 0:
            continue
        rows.append((
            f"{tenant.first_name} {tenant.last_name}".strip(),
            prop.name, unit.unit_number, invoice.id,
            invoice.due_date, (today - invoice.due_date).days,
            rent, late_fee, paid, outstanding, prop.id,
        ))
    return ReportPayload(
        title=f"Tenant rent delinquency as of {today.isoformat()}",
        filename=f"tenant-rent-delinquency-{today.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
