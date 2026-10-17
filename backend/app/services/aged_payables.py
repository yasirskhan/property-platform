"""Current-state payable bill aging; no fictitious historical balance reconstruction.

Bill.amount_paid and status are mutable current metadata, so the reference
date must be today. Posted accrual bill registration is checked against the
same-organization original BILL GL transaction and payable LIABILITY account.
This is NOT a reconstructed as-of GL liability, cleared payment schedule or
historical aging report. No accounting writes.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param,
)
from app.services.reporting_basis import get_accounting_basis


HEADERS = (
    "Bill ID", "Bill Number", "Recorded Payee", "Bill Date", "Due Date",
    "Recorded Status", "Current Recorded Unpaid", "Days Past Due", "Age Bucket",
)
BUCKETS = (
    "NOT YET DUE", "DUE TODAY", "1-30 DAYS", "31-60 DAYS",
    "61-90 DAYS", "91+ DAYS", "DUE DATE NOT RECORDED",
)


def _bucket(as_of: date, due: date | None) -> tuple[str, int | str]:
    if due is None:
        return "DUE DATE NOT RECORDED", ""
    age = (as_of - due).days
    if age < 0:
        return "NOT YET DUE", 0
    if age == 0:
        return "DUE TODAY", 0
    if age <= 30:
        return "1-30 DAYS", age
    if age <= 60:
        return "31-60 DAYS", age
    if age <= 90:
        return "61-90 DAYS", age
    return "91+ DAYS", age


def build_aged_payables(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"as_of"}:
        raise ReportDeliveryError("Unsupported aged payables parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Aged payables permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.PAYABLES"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Aged payables permission required")
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError(
            "Current posted accrual payables require ACCRUAL basis; CASH payable aging is unavailable"
        )
    today = date.today()
    requested_date = _date_param(parameters, "as_of")
    if requested_date is not None and requested_date != today:
        raise ReportDeliveryError(
            "Historical or future aging is unavailable from current bill payment metadata; use today's date"
        )
    records = (
        db.query(Bill, GLTransaction)
        .join(GLTransaction, GLTransaction.id == Bill.gl_transaction_id)
        .filter(
            Bill.organization_id == organization_id,
            Bill.is_active.is_(True),
            Bill.deleted_at.is_(None),
            Bill.is_reversed.is_(False),
            Bill.status != "VOID",
            Bill.bill_date <= today,
            GLTransaction.organization_id == organization_id,
            GLTransaction.transaction_type == "BILL",
            GLTransaction.is_reversed.is_(False),
        )
        .order_by(Bill.due_date.asc(), Bill.bill_date.asc(), Bill.id.asc())
        .all()
    )

    lines: list[tuple[object, ...]] = []
    buckets = {name: Decimal("0") for name in BUCKETS}
    total = Decimal("0")
    for bill, _posted in records:
        if bill.status not in {"UNPAID", "PARTIAL", "PAID"}:
            raise ReportDeliveryError("Unrecognized recorded bill payment status")
        amount = Decimal(bill.amount or 0)
        paid = Decimal(bill.amount_paid or 0)
        if amount <= 0 or paid < 0 or paid > amount:
            raise ReportDeliveryError("Invalid recorded bill payment amounts")
        if bill.status == "PAID":
            if paid != amount:
                raise ReportDeliveryError("Paid bill metadata does not reconcile")
            continue
        if bill.status == "UNPAID" and paid != 0:
            raise ReportDeliveryError("Unpaid bill metadata does not reconcile")
        if bill.status == "PARTIAL" and (paid <= 0 or paid >= amount):
            raise ReportDeliveryError("Partial bill metadata does not reconcile")
        payable = db.query(GLAccount.id).filter(
            GLAccount.id == bill.payable_gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "LIABILITY",
        ).first()
        if payable is None:
            raise ReportDeliveryError("Payable GL account mapping needs review")
        outstanding = amount - paid
        label, age = _bucket(today, bill.due_date)
        buckets[label] += outstanding
        total += outstanding
        lines.append((
            bill.id, bill.bill_number or "", bill.payee_name, bill.bill_date,
            bill.due_date or "", bill.status, outstanding, age, label,
        ))
    for label in BUCKETS:
        lines.append(("BUCKET", label, "", "", "", "", buckets[label], "", ""))
    lines.append(("TOTAL", "CURRENT RECORDED UNPAID", "", "", "", "", total, "", ""))
    return ReportPayload(
        title=(
            f"Current recorded posted accrual bill payables, aged on {today.isoformat()}; "
            "NOT a historic as-of ledger or confirmed cleared payments; "
            "due-date buckets use today's unpaid amounts"
        ),
        filename=f"current-recorded-aged-payables-{today.isoformat()}.csv",
        headers=HEADERS, rows=tuple(lines),
    )
