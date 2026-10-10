"""Current recorded AP bill activity for explicitly linked vendor accounts.

This report is NOT a reconstructed cash ledger, tax 1099 register or inference
that free-text bill payees belong to an account. It excludes unlinked,
reversed, void and deleted bill records. Recorded paid amounts are the
bill's existing payment metadata, never generated or reposted by reporting.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)

HEADERS = (
    "Bill Date", "Vendor User ID", "Vendor Recorded Name",
    "Bill ID", "Bill Number", "Bill Status",
    "Bill Amount", "Recorded Paid", "Recorded Unpaid",
)


def build_vendor_ledger(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    """Keep financial scope narrower than the vendor contact directory."""
    if set(parameters) - {"vendor_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported vendor ledger parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Vendor ledger permission required")
    for key in ("REPORTING.ALL", "PEOPLE.VENDORS", "ACCOUNTING.PAYABLES"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Vendor ledger permission required")
    vendor_id = _int_param(parameters, "vendor_id")
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    vendor_query = db.query(User).filter(
        User.organization_id == organization_id,
        User.role == UserRole.VENDOR,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if vendor_id is not None:
        vendor_query = vendor_query.filter(User.id == vendor_id)
        if vendor_query.first() is None:
            raise ReportDeliveryError("Vendor not found")
    visible_vendor_ids = vendor_query.with_entities(User.id)
    records = db.query(Bill, User).join(
        User, Bill.payee_user_id == User.id,
    ).filter(
        Bill.organization_id == organization_id,
        Bill.payee_user_id.in_(visible_vendor_ids),
        Bill.is_active.is_(True),
        Bill.deleted_at.is_(None),
        Bill.is_reversed.is_(False),
        Bill.status != "VOID",
    )
    if date_from is not None:
        records = records.filter(Bill.bill_date >= date_from)
    if date_to is not None:
        records = records.filter(Bill.bill_date <= date_to)
    records = records.order_by(
        Bill.bill_date.asc(), Bill.id.asc(),
    ).all()
    rows = []
    for bill, vendor in records:
        amount = Decimal(bill.amount)
        paid = Decimal(bill.amount_paid or 0)
        # Do not silently report corrupted/overpaid payable metadata as debt.
        if amount < 0 or paid < 0 or paid > amount:
            raise ReportDeliveryError("Invalid recorded bill payment amounts")
        rows.append((
            bill.bill_date, vendor.id,
            f"{vendor.first_name} {vendor.last_name}".strip(),
            bill.id, bill.bill_number or "", bill.status,
            amount, paid, amount - paid,
        ))
    return ReportPayload(
        title="Linked vendor payable-bill register (current recorded amounts; not a GL or cash payment ledger)",
        filename="vendor-linked-payable-bills.csv",
        headers=HEADERS, rows=tuple(rows),
    )
