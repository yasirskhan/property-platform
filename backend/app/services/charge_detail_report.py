"""Current recorded standalone tenant Charge detail, not GL-posted AR.

Charge.amount_paid and is_paid are mutable metadata. RentInvoice and receipt
rows are deliberately not combined because late-fee balances may overlap.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)


HEADERS = (
    "Charge ID", "Charge Date", "Tenant", "Property", "Unit",
    "Recorded Description", "GL Number", "GL Account",
    "Recorded Amount", "Current Recorded Paid", "Current Recorded Balance",
    "Recorded Paid Flag", "Balance Interpretation", "Tenant ID", "Property ID",
)


def build_charge_detail(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"charge_id", "tenant_id", "property_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported Charge Detail parameter")
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role or "")
    role = role.upper()
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or role not in {"ADMIN", "MANAGER"}
    ):
        raise ReportDeliveryError("Charge Detail permission required")
    for key in ("REPORTING.ALL", "LEASING", "ACCOUNTING.CHARGES", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Charge Detail permission required")
    charge_id = _int_param(parameters, "charge_id")
    tenant_id = _int_param(parameters, "tenant_id")
    property_id = _int_param(parameters, "property_id")
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    tenant_q = db.query(User.id).filter(
        User.organization_id == organization_id, User.role == UserRole.TENANT,
        User.is_active.is_(True), User.deleted_at.is_(None),
    )
    if tenant_id is not None and tenant_q.filter(User.id == tenant_id).first() is None:
        raise ReportDeliveryError("Tenant not found")
    visible = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    )
    if role == "MANAGER":
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
        db.query(Charge, User, Property, Unit)
        .join(User, User.id == Charge.tenant_user_id)
        .outerjoin(Property, and_(
            Property.id == Charge.property_id,
            Property.organization_id == organization_id,
            Property.is_active.is_(True), Property.deleted_at.is_(None),
        ))
        .outerjoin(Unit, and_(
            Unit.id == Charge.unit_id,
            Unit.property_id == Charge.property_id,
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        ))
        .filter(
            Charge.organization_id == organization_id,
            Charge.is_active.is_(True), Charge.deleted_at.is_(None),
            User.id.in_(tenant_q),
            or_(Charge.property_id.is_(None), Property.id.in_(visible)),
        )
    )
    if role == "MANAGER" or property_id is not None:
        query = query.filter(Charge.property_id.in_(visible))
    if tenant_id is not None:
        query = query.filter(Charge.tenant_user_id == tenant_id)
    if charge_id is not None:
        query = query.filter(Charge.id == charge_id)
    if date_from is not None:
        query = query.filter(Charge.charge_date >= date_from)
    if date_to is not None:
        query = query.filter(Charge.charge_date <= date_to)

    records = query.order_by(Charge.charge_date.asc(), Charge.id.asc()).limit(5001).all()
    if len(records) > 5000:
        raise ReportDeliveryError("Narrow Charge Detail filters before exporting")
    if charge_id is not None and not records:
        raise ReportDeliveryError("Charge not found")
    if role == "MANAGER" and tenant_id is not None and not records:
        raise ReportDeliveryError("Tenant not found")

    rows: list[tuple[object, ...]] = []
    total_billed = total_paid = total_balance = Decimal("0")
    for charge, tenant, prop, unit in records:
        if charge.unit_id is not None and unit is None:
            raise ReportDeliveryError("Charge unit mapping needs review")
        account = db.query(GLAccount).filter(
            GLAccount.id == charge.gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "INCOME",
        ).first()
        if account is None:
            raise ReportDeliveryError("Charge GL account mapping needs review")
        billed = Decimal(charge.amount or 0)
        paid = Decimal(charge.amount_paid or 0)
        if billed < 0 or paid < 0:
            raise ReportDeliveryError("Invalid recorded Charge amounts")
        balance = billed - paid
        if balance < 0:
            interpretation = "RECORDED CREDIT / OVERPAYMENT; VERIFY"
        elif balance == 0:
            interpretation = "RECORDED ZERO BALANCE"
        else:
            interpretation = "RECORDED UNPAID"
        if bool(charge.is_paid) != (balance <= 0):
            interpretation += "; PAID FLAG NEEDS REVIEW"
        total_billed += billed
        total_paid += paid
        total_balance += balance
        rows.append((
            charge.id, charge.charge_date,
            f"{tenant.first_name} {tenant.last_name}".strip(),
            prop.name if prop is not None else "Unallocated organization charge",
            unit.unit_number if unit is not None else "",
            charge.description, account.gl_number, account.name,
            billed, paid, balance, "Yes" if charge.is_paid else "No",
            interpretation, tenant.id, prop.id if prop is not None else "",
        ))
    rows.append((
        "TOTAL", "", "", "", "", "", "", "",
        total_billed, total_paid, total_balance, "", "", "", "",
    ))
    return ReportPayload(
        title=(
            f"Standalone Charge detail at current recorded amounts on {date.today().isoformat()}; "
            "NOT posted GL receivables, historical balances or verified cleared payments; "
            "rent invoices and their late fees deliberately excluded"
        ),
        filename=f"current-recorded-charge-detail-{date.today().isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
