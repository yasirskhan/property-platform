"""Current recorded rent invoice aging, not historical or GL-reconciled AR.

Invoice.amount_paid is a mutable current balance snapshot and RentInvoice has no
verified posted AR GL pointer. Standalone Charge balances (including possibly
duplicate late fees) remain in their distinct verified reports.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.lease import InvoiceStatus, Lease, RentInvoice
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param, _int_param


HEADERS = (
    "Tenant", "Property", "Unit", "Invoice ID", "Due Date",
    "Recorded Status", "Recorded Rent", "Recorded Late Fee",
    "Recorded Paid", "Current Recorded Unpaid", "Days Past Due",
    "Age Bucket", "Property ID",
)
BUCKETS = (
    "NOT YET DUE", "DUE TODAY", "1-30 DAYS", "31-60 DAYS",
    "61-90 DAYS", "91+ DAYS",
)


def _bucket(as_of: date, due: date) -> tuple[str, int]:
    days = (as_of - due).days
    if days < 0:
        return "NOT YET DUE", 0
    if days == 0:
        return "DUE TODAY", 0
    if days <= 30:
        return "1-30 DAYS", days
    if days <= 60:
        return "31-60 DAYS", days
    if days <= 90:
        return "61-90 DAYS", days
    return "91+ DAYS", days


def build_aged_receivables(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"as_of", "property_id", "tenant_id"}:
        raise ReportDeliveryError("Unsupported aged receivables parameter")
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role or "")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or role.upper() not in {"ADMIN", "MANAGER"}
    ):
        raise ReportDeliveryError("Aged receivables permission required")
    for permission in ("REPORTING.ALL", "LEASING"):
        if not permission_allows_user(db, user=current_user, menu_key=permission):
            raise ReportDeliveryError("Aged receivables permission required")

    today = date.today()
    as_of = _date_param(parameters, "as_of")
    if as_of is not None and as_of != today:
        raise ReportDeliveryError(
            "Historical or future receivable balances cannot be reconstructed from current invoice payment metadata"
        )
    property_id = _int_param(parameters, "property_id")
    tenant_id = _int_param(parameters, "tenant_id")
    visible = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    )
    if role.upper() == "MANAGER":
        assignments = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        visible = visible.filter(Property.id.in_(assignments))
    if property_id is not None:
        visible = visible.filter(Property.id == property_id)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")

    query = (
        db.query(RentInvoice, Property, Unit, User)
        .join(Lease, Lease.id == RentInvoice.lease_id)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .join(User, User.id == Lease.tenant_id)
        .filter(
            Property.id.in_(visible),
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True), User.deleted_at.is_(None),
            RentInvoice.status != InvoiceStatus.VOID,
        )
    )
    if tenant_id is not None:
        query = query.filter(User.id == tenant_id)
    query = query.order_by(RentInvoice.due_date.asc(), Property.id.asc(), RentInvoice.id.asc())

    rows: list[tuple[object, ...]] = []
    totals = {name: Decimal("0") for name in BUCKETS}
    grand_total = Decimal("0")
    for invoice, prop, unit, tenant in query.all():
        rent = Decimal(invoice.amount_due or 0)
        fee = Decimal(invoice.late_fee or 0)
        paid = Decimal(invoice.amount_paid or 0)
        billed = rent + fee
        if rent < 0 or fee < 0 or paid < 0 or paid > billed:
            raise ReportDeliveryError("Invalid recorded rent invoice amounts")
        unpaid = billed - paid
        if invoice.status == InvoiceStatus.PAID:
            if unpaid != 0:
                raise ReportDeliveryError("Paid invoice status does not reconcile")
            continue
        if unpaid == 0:
            continue
        label, days = _bucket(today, invoice.due_date)
        totals[label] += unpaid
        grand_total += unpaid
        rows.append((
            f"{tenant.first_name} {tenant.last_name}".strip(), prop.name,
            unit.unit_number, invoice.id, invoice.due_date, invoice.status.value,
            rent, fee, paid, unpaid, days, label, prop.id,
        ))
    if role.upper() == "MANAGER" and tenant_id is not None and not rows:
        raise ReportDeliveryError("Tenant not found")
    for label in BUCKETS:
        rows.append(("BUCKET", label, "", "", "", "", "", "", "", totals[label], "", "", ""))
    rows.append(("TOTAL", "CURRENT RECORDED RENT INVOICE UNPAID", "", "", "", "",
                 "", "", "", grand_total, "", "", ""))
    return ReportPayload(
        title=(
            f"Current recorded rent invoice balances aged on {today.isoformat()}; "
            "NOT historical, not posted GL AR, not verified payments; "
            "standalone Charges deliberately excluded to avoid double counting"
        ),
        filename=f"current-recorded-aged-receivables-{today.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
