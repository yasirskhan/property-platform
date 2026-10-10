"""Read-only posted bill headers and verified line breakdown; not paid-check history."""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)


HEADERS = (
    "Record", "Bill ID", "Bill Number", "Vendor Reference",
    "Bill Date", "Due Date", "Recorded Payee", "Recorded Status",
    "GL Account", "Account Name", "Line Description", "Line Amount",
    "Bill Amount", "Recorded Paid", "Current Recorded Unpaid",
)


def build_bill_detail(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"bill_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported bill detail parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Bill detail permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.PAYABLES", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Bill detail permission required")

    bill_id = _int_param(parameters, "bill_id")
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    if bill_id is not None:
        exists = db.query(Bill.id).filter(
            Bill.id == bill_id, Bill.organization_id == organization_id,
            Bill.is_active.is_(True), Bill.deleted_at.is_(None),
            Bill.is_reversed.is_(False), Bill.status != "VOID",
        ).first()
        if exists is None:
            raise ReportDeliveryError("Bill not found")

    q = (
        db.query(Bill, GLTransaction)
        .join(GLTransaction, GLTransaction.id == Bill.gl_transaction_id)
        .filter(
            Bill.organization_id == organization_id,
            Bill.is_active.is_(True), Bill.deleted_at.is_(None),
            Bill.is_reversed.is_(False), Bill.status != "VOID",
            GLTransaction.organization_id == organization_id,
            GLTransaction.transaction_type == "BILL",
            GLTransaction.is_reversed.is_(False),
            GLTransaction.reversal_of_id.is_(None),
        )
    )
    if bill_id is not None:
        q = q.filter(Bill.id == bill_id)
    if date_from is not None:
        q = q.filter(Bill.bill_date >= date_from)
    if date_to is not None:
        q = q.filter(Bill.bill_date <= date_to)
    records = q.order_by(Bill.bill_date.asc(), Bill.id.asc()).all()
    if bill_id is not None and not records:
        raise ReportDeliveryError("Bill not found")
    if len(records) > 5000:
        raise ReportDeliveryError("Narrow bill detail date filters before exporting")

    rows: list[tuple[object, ...]] = []
    for bill, _transaction in records:
        if bill.status not in {"UNPAID", "PARTIAL", "PAID"}:
            raise ReportDeliveryError("Unrecognized bill payment status")
        amount = Decimal(bill.amount or 0)
        paid = Decimal(bill.amount_paid or 0)
        if amount <= 0 or paid < 0 or paid > amount:
            raise ReportDeliveryError("Invalid recorded bill amounts")
        if bill.status == "UNPAID" and paid != 0:
            raise ReportDeliveryError("Unpaid bill metadata does not reconcile")
        if bill.status == "PAID" and paid != amount:
            raise ReportDeliveryError("Paid bill metadata does not reconcile")
        if bill.status == "PARTIAL" and not (0 < paid < amount):
            raise ReportDeliveryError("Partial bill metadata does not reconcile")

        payable = db.query(GLAccount).filter(
            GLAccount.id == bill.payable_gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "LIABILITY",
        ).first()
        if payable is None:
            raise ReportDeliveryError("Payable GL account mapping needs review")

        parts = db.query(BillLine).filter(BillLine.bill_id == bill.id).order_by(BillLine.id).all()
        if not parts:
            raise ReportDeliveryError("Bill has no verified line breakdown")
        verified: list[tuple[BillLine, GLAccount]] = []
        total = Decimal("0")
        for line in parts:
            if line.organization_id != organization_id:
                raise ReportDeliveryError("Bill line organization needs review")
            gl = db.query(GLAccount).filter(
                GLAccount.id == line.gl_account_id,
                GLAccount.organization_id == organization_id,
            ).first()
            if gl is None:
                raise ReportDeliveryError("Bill line GL mapping needs review")
            value = Decimal(line.amount or 0)
            if value <= 0:
                raise ReportDeliveryError("Invalid recorded bill line amount")
            total += value
            verified.append((line, gl))
        if total != amount:
            raise ReportDeliveryError("Recorded bill line sum does not match bill amount")

        rows.append((
            "BILL", bill.id, bill.bill_number or "", bill.reference_number or "",
            bill.bill_date, bill.due_date or "", bill.payee_name, bill.status,
            payable.gl_number, payable.name, "", "",
            amount, paid, amount - paid,
        ))
        # Child rows never repeat the parent amount or unpaid balance.
        for line, gl in verified:
            rows.append((
                "LINE", bill.id, "", "", "", "", "", "",
                gl.gl_number, gl.name, line.description or "",
                Decimal(line.amount), "", "", "",
            ))

    return ReportPayload(
        title=(
            "Recorded posted bill and GL-account line detail; current mutable "
            "payment metadata only, NOT cleared payment history or historical AP"
        ),
        filename="posted-bill-detail.csv",
        headers=HEADERS, rows=tuple(rows),
    )
