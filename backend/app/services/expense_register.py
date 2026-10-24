"""Expense Register: dated posted accrual EXPENSE GL entries, read-only.

Not PropertyExpense metadata, checks paid, bank cash, or inferred cash basis.
Include signed credits and reversal entries; archival does not erase history.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)
from app.services.reporting_basis import get_accounting_basis

HEADERS = (
    "Posted Date", "GL Transaction ID", "GL Entry ID",
    "Recorded Transaction Type", "Recorded Reference", "Expense GL Number",
    "Expense GL Account", "Recorded Entry Description",
    "Posted Debit", "Posted Credit", "Signed Net Expense",
)


def build_expense_register(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"date_from", "date_to", "account_id"}:
        raise ReportDeliveryError("Unsupported Expense Register parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Expense Register permission required")
    for permission in ("REPORTING.ALL", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=permission):
            raise ReportDeliveryError("Expense Register permission required")
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError(
            "Expense Register requires ACCRUAL basis; CASH-basis expense classification unavailable"
        )
    start = _date_param(parameters, "date_from")
    end = _date_param(parameters, "date_to")
    if start is None or end is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > end:
        raise ReportDeliveryError("date_from cannot be after date_to")
    account_id = _int_param(parameters, "account_id")
    if account_id is not None and db.query(GLAccount.id).filter(
        GLAccount.id == account_id, GLAccount.organization_id == organization_id,
        GLAccount.account_type == "EXPENSE",
    ).first() is None:
        raise ReportDeliveryError("Expense GL account not found")

    query = db.query(GLEntry, GLTransaction, GLAccount).join(
        GLTransaction, GLTransaction.id == GLEntry.transaction_id,
    ).join(
        GLAccount, GLAccount.id == GLEntry.gl_account_id,
    ).filter(
        GLEntry.organization_id == organization_id,
        GLTransaction.organization_id == organization_id,
        GLAccount.organization_id == organization_id,
        GLAccount.account_type == "EXPENSE",
        GLTransaction.transaction_date >= start,
        GLTransaction.transaction_date <= end,
    )
    if account_id is not None:
        query = query.filter(GLEntry.gl_account_id == account_id)
    records = query.order_by(
        GLTransaction.transaction_date.asc(), GLTransaction.id.asc(), GLEntry.id.asc(),
    ).limit(5001).all()
    if len(records) > 5000:
        raise ReportDeliveryError("Narrow Expense Register filters before exporting")

    rows: list[tuple[object, ...]] = []
    total_debit = total_credit = Decimal("0")
    for entry, txn, gl in records:
        dr, cr = Decimal(entry.debit or 0), Decimal(entry.credit or 0)
        if dr < 0 or cr < 0 or (dr == 0 and cr == 0) or (dr > 0 and cr > 0):
            raise ReportDeliveryError("Expense entry debit/credit requires review")
        total_debit += dr
        total_credit += cr
        rows.append((
            txn.transaction_date, txn.id, entry.id,
            txn.transaction_type, txn.reference_number or "",
            gl.gl_number, gl.name, entry.description or "",
            dr, cr, dr - cr,
        ))
    rows.append((
        "", "", "", "", "TOTAL", "", "", "",
        total_debit, total_credit, total_debit - total_credit,
    ))
    return ReportPayload(
        title=(
            f"Posted accrual expense register {start.isoformat()} to {end.isoformat()}; "
            "signed GL debit-minus-credit including reversals; "
            "NOT cleared bank spending, PropertyExpense metadata or cash-basis expense"
        ),
        filename=f"posted-accrual-expense-register-{start.isoformat()}-{end.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
