"""Tenant invoice and standalone-charge CURRENT balance schedule.

RentInvoice.amount_paid and Charge.amount_paid are authoritative CURRENT
snapshots for their respective source records. Legacy Payment rows and
accounting Receipt/ReceiptLine can refer to the same money or unrelated
cash flows; deliberately do NOT concatenate them into fictitious
transaction history. Not a historically reconstructed GL ledger.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.lease import InvoiceStatus, Lease, RentInvoice
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param

HEADERS = (
    "Document Date", "Tenant", "Property", "Unit", "Source", "Document ID",
    "Description", "Billed Amount", "Recorded Paid", "Current Balance",
    "Tenant ID", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def build_tenant_ledger(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Tenant ledger is not available to this user")
    # The directory exposes standalone accounting Charge rows: do not
    # bypass the same CHARGES permission enforced by its own API.
    if not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.CHARGES"):
        raise ReportDeliveryError("Tenant ledger permission required")
    if set(parameters) - {"tenant_id", "property_id"}:
        raise ReportDeliveryError("Unsupported tenant ledger parameter")
    tenant_id = _int_param(parameters, "tenant_id")
    property_id = _int_param(parameters, "property_id")
    tenant_q = db.query(User).filter(
        User.organization_id == organization_id,
        User.role == UserRole.TENANT,
        User.deleted_at.is_(None),
    )
    if tenant_id is not None:
        tenant_q = tenant_q.filter(User.id == tenant_id)
        if tenant_q.first() is None:
            raise ReportDeliveryError("Tenant not found")
    allowed_properties = db.query(Property.id).filter(Property.organization_id == organization_id)
    if role == "MANAGER":
        assignments = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        allowed_properties = allowed_properties.filter(
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            Property.id.in_(assignments),
        )
    if property_id is not None:
        allowed_properties = allowed_properties.filter(Property.id == property_id)
        if allowed_properties.first() is None:
            raise ReportDeliveryError("Property not found")

    # An invoice belongs to exactly one lease/tenant/unit/property; do not
    # join independent Receipt rows which could represent the same payment.
    invoice_q = (
        db.query(RentInvoice, Lease, Unit, Property, User)
        .join(Lease, Lease.id == RentInvoice.lease_id)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .join(User, User.id == Lease.tenant_id)
        .filter(
            Property.id.in_(allowed_properties),
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.deleted_at.is_(None),
            RentInvoice.status != InvoiceStatus.VOID,
        )
    )
    if tenant_id is not None:
        invoice_q = invoice_q.filter(User.id == tenant_id)
    rows: list[tuple[object, ...]] = []
    for invoice, lease, unit, prop, tenant in invoice_q.all():
        billed = Decimal(invoice.amount_due or 0) + Decimal(invoice.late_fee or 0)
        paid = Decimal(invoice.amount_paid or 0)
        rows.append((
            invoice.due_date, f"{tenant.first_name} {tenant.last_name}".strip(),
            prop.name, unit.unit_number, "Rent invoice", invoice.id,
            f"Rent invoice (due {invoice.due_date.isoformat()})",
            billed, paid, billed - paid, tenant.id, prop.id,
        ))
    # Standalone charges are separate from invoices and may be unallocated
    # to any property. Only org ADMIN may see that unallocated contact.
    charge_q = (
        db.query(Charge, Property, Unit, User)
        .join(User, User.id == Charge.tenant_user_id)
        .outerjoin(Property, and_(
            Property.id == Charge.property_id,
            Property.organization_id == organization_id,
        ))
        .outerjoin(Unit, and_(
            Unit.id == Charge.unit_id, Unit.property_id == Charge.property_id,
        ))
        .filter(
            Charge.organization_id == organization_id,
            Charge.is_active.is_(True),
            Charge.deleted_at.is_(None),
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.deleted_at.is_(None),
        )
    )
    if role == "MANAGER" or property_id is not None:
        charge_q = charge_q.filter(Charge.property_id.in_(allowed_properties))
    else:
        charge_q = charge_q.filter(or_(
            Charge.property_id.is_(None),
            Charge.property_id.in_(allowed_properties),
        ))
    if tenant_id is not None:
        charge_q = charge_q.filter(User.id == tenant_id)
    for charge, prop, unit, tenant in charge_q.all():
        billed = Decimal(charge.amount or 0)
        paid = Decimal(charge.amount_paid or 0)
        rows.append((
            charge.charge_date,
            f"{tenant.first_name} {tenant.last_name}".strip(),
            prop.name if prop is not None else "Unallocated organization charge",
            unit.unit_number if unit is not None else "",
            "Standalone charge", charge.id, charge.description,
            billed, paid, billed - paid, tenant.id, prop.id if prop is not None else "",
        ))
    rows.sort(key=lambda x: (x[0], x[10], x[11] if isinstance(x[11], int) else 0, x[4], x[5]))
    # A manager's tenant_id filter must not disclose whether a user exists
    # outside its assignments. Same not-found as foreign/non-tenant ID.
    if role == "MANAGER" and tenant_id is not None and not rows:
        raise ReportDeliveryError("Tenant not found")
    return ReportPayload(
        title=f"Tenant current charge and rent balances as of {date.today().isoformat()}",
        filename=f"tenant-current-ledger-{date.today().isoformat()}.csv",
        headers=HEADERS,
        rows=tuple(rows),
    )
