"""Security deposit liability detail from posted GL only.

An entry can be property-tagged or unallocated. GLEntry does not carry
tenant identity, and lease.security_deposit is a contract figure, not a
bank-held balance. NEVER describe this as reconciled custodial cash.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.accounting_key_account import AccountingKeyAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)

REPORT_KEY = "tenant.security_deposit_funds_detail"
HEADERS = (
    "Posting Date", "Property", "Unit", "GL Number", "Account",
    "Entry ID", "Reference", "Liability Debit", "Liability Credit",
    "Net Liability Change", "Allocation", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def build_security_deposit_funds_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Security deposit report is not available to this user")
    if set(parameters) - {"as_of", "property_id"}:
        raise ReportDeliveryError("Unsupported security deposit report parameter")
    as_of = _date_param(parameters, "as_of") or date.today()
    if as_of > date.today():
        raise ReportDeliveryError("as_of cannot be in the future")
    property_id = _int_param(parameters, "property_id")

    # Current org-ownership is mandatory even for cross-org property ID probes.
    # Admin may see historical inactive property allocations; managers only
    # get active, nondeleted, explicitly assigned properties.
    visible = db.query(Property.id).filter(Property.organization_id == organization_id)
    if role == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        visible = visible.filter(
            Property.id.in_(assigned), Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
    if property_id is not None:
        visible = visible.filter(Property.id == property_id)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")

    # Include the canonical security deposit liability (2101) plus
    # organization-configured owner-held DEPOSIT_LIABILITY key accounts.
    # Do not infer deposit accounts by account names, cash accounts or leases.
    configured = db.query(AccountingKeyAccount.gl_account_id).filter(
        AccountingKeyAccount.organization_id == organization_id,
        AccountingKeyAccount.key_type == "DEPOSIT_LIABILITY",
    )
    accounts = db.query(GLAccount.id).filter(
        GLAccount.organization_id == organization_id,
        GLAccount.account_type == "LIABILITY",
        or_(GLAccount.gl_number == "2101", GLAccount.id.in_(configured)),
    )

    query = (
        db.query(GLEntry, GLTransaction, GLAccount, Property, Unit)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .join(GLAccount, GLAccount.id == GLEntry.gl_account_id)
        .outerjoin(Property, Property.id == GLEntry.property_id)
        .outerjoin(Unit, Unit.id == GLEntry.unit_id)
        .filter(
            GLEntry.organization_id == organization_id,
            GLTransaction.organization_id == organization_id,
            GLAccount.id.in_(accounts),
            GLTransaction.transaction_date <= as_of,
        )
    )
    if role == "MANAGER" or property_id is not None:
        query = query.filter(GLEntry.property_id.in_(visible))
    else:
        # An admin can review unallocated ledger lines, but must never
        # receive property data from another organization.
        query = query.filter(or_(
            GLEntry.property_id.is_(None),
            GLEntry.property_id.in_(visible),
        ))
    query = query.order_by(
        GLTransaction.transaction_date.asc(), GLEntry.id.asc(),
    )
    rows: list[tuple[object, ...]] = []
    for entry, transaction, account, prop, unit in query.all():
        # A unit tag is displayed only when its property tag is coherent.
        unit_number = (unit.unit_number if (
            unit is not None and prop is not None
            and unit.property_id == prop.id
        ) else "")
        allocated = prop is not None
        rows.append((
            transaction.transaction_date,
            prop.name if allocated else "Unallocated",
            unit_number, account.gl_number, account.name,
            entry.id, transaction.reference_number or "",
            Decimal(entry.debit or 0), Decimal(entry.credit or 0),
            Decimal(entry.credit or 0) - Decimal(entry.debit or 0),
            "Property tagged" if allocated else "Unallocated; review",
            prop.id if allocated else "",
        ))
    return ReportPayload(
        title=f"Security deposit GL liability detail through {as_of.isoformat()}",
        filename=f"security-deposit-liability-detail-{as_of.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
