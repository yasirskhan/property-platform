"""Dated, read-only income statement from actual posted accrual GL lines.

Revenue naturally carries credits; expenses naturally carry debits. Negative
account balances (returns, credits, reversals) stay signed and visible.
No bank deposits, bill status, payment snapshots or inferred GAAP allocations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _bool_param, _date_param,
)
from app.services.reporting_basis import get_accounting_basis

HEADERS = (
    "Section", "GL Number", "Recorded GL Account", "Posted Debits",
    "Posted Credits", "Natural Posted Balance",
)


def build_income_statement(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"date_from", "date_to", "include_zero"}:
        raise ReportDeliveryError("Unsupported income statement parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Income statement permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Income statement permission required")
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError(
            "Income statement requires posted ACCRUAL GL; CASH-basis P&L is not available"
        )
    start = _date_param(parameters, "date_from")
    end = _date_param(parameters, "date_to")
    if start is None or end is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > end:
        raise ReportDeliveryError("date_from cannot be after date_to")
    include_zero = _bool_param(parameters, "include_zero", False)

    entries = db.query(
        GLEntry.gl_account_id,
        func.coalesce(func.sum(GLEntry.debit), 0),
        func.coalesce(func.sum(GLEntry.credit), 0),
    ).join(
        GLTransaction, GLTransaction.id == GLEntry.transaction_id,
    ).join(
        GLAccount, GLAccount.id == GLEntry.gl_account_id,
    ).filter(
        GLEntry.organization_id == organization_id,
        GLTransaction.organization_id == organization_id,
        GLAccount.organization_id == organization_id,
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
        GLTransaction.transaction_date >= start,
        GLTransaction.transaction_date <= end,
    )
    totals = {
        int(account_id): (Decimal(debit or 0), Decimal(credit or 0))
        for account_id, debit, credit in entries.group_by(GLEntry.gl_account_id).all()
    }
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == organization_id,
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
    ).order_by(GLAccount.gl_number.asc(), GLAccount.id.asc()).all()

    revenue = expense = Decimal("0")
    income_rows: list[tuple[object, ...]] = []
    expense_rows: list[tuple[object, ...]] = []
    for gl in accounts:
        debit, credit = totals.get(gl.id, (Decimal("0"), Decimal("0")))
        if not include_zero and debit == 0 and credit == 0:
            continue
        if gl.account_type == "INCOME":
            natural = credit - debit
            revenue += natural
            income_rows.append(("INCOME", gl.gl_number, gl.name, debit, credit, natural))
        else:
            natural = debit - credit
            expense += natural
            expense_rows.append(("EXPENSE", gl.gl_number, gl.name, debit, credit, natural))
    net = revenue - expense
    rows = (
        *income_rows,
        ("TOTAL POSTED INCOME", "", "", "", "", revenue),
        *expense_rows,
        ("TOTAL POSTED EXPENSE", "", "", "", "", expense),
        ("NET POSTED INCOME LESS EXPENSE", "", "", "", "", net),
    )
    return ReportPayload(
        title=(
            f"Unaudited posted accrual income statement {start.isoformat()} "
            f"to {end.isoformat()}; natural signed balances, including reversals; "
            "no CASH-basis translation or unposted adjustments"
        ),
        filename=f"posted-income-statement-{start.isoformat()}-{end.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
