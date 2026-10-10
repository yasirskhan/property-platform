"""Read-only expense GL distribution using genuine posted accrual entries.

Account labels come only from the chart of accounts. Expense means account
type EXPENSE, not payment date, categorized bank feed or an inferred bill.
Negative posted net expenses and reversal entries remain visible.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
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
    "Expense GL Number", "Expense GL Account", "Posted Debits",
    "Posted Credits / Reversals", "Net Posted Expense",
    "Share Of Net Expense (%)",
)


def build_expense_distribution(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"date_from", "date_to", "include_zero"}:
        raise ReportDeliveryError("Unsupported expense distribution parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Expense distribution permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Expense distribution permission required")
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError(
            "Posted expense distribution requires ACCRUAL basis; CASH expense classification unavailable"
        )

    start = _date_param(parameters, "date_from")
    finish = _date_param(parameters, "date_to")
    if start is None or finish is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > finish:
        raise ReportDeliveryError("date_from cannot be after date_to")
    include_zero = _bool_param(parameters, "include_zero", False)

    activity = db.query(
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
        GLAccount.account_type == "EXPENSE",
        GLTransaction.transaction_date >= start,
        GLTransaction.transaction_date <= finish,
    )
    sums = {
        int(gl_id): (Decimal(dr or 0), Decimal(cr or 0))
        for gl_id, dr, cr in activity.group_by(GLEntry.gl_account_id).all()
    }
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == organization_id,
        GLAccount.account_type == "EXPENSE",
    ).order_by(GLAccount.gl_number.asc(), GLAccount.id.asc()).all()
    observed = []
    total_dr = total_cr = Decimal("0")
    for gl in accounts:
        if gl.id not in sums and not include_zero:
            continue
        dr, cr = sums.get(gl.id, (Decimal("0"), Decimal("0")))
        total_dr += dr
        total_cr += cr
        observed.append((gl.gl_number, gl.name, dr, cr, dr - cr))
    total = total_dr - total_cr
    rows = []
    for gl_num, gl_name, dr, cr, net in observed:
        share = (
            (net / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if total > 0 else "N/A"
        )
        rows.append((gl_num, gl_name, dr, cr, net, share))
    rows.append((
        "TOTAL", "Recorded posted expense accounts", total_dr, total_cr,
        total, Decimal("100.00") if total > 0 else "N/A",
    ))
    return ReportPayload(
        title=(
            f"Posted accrual expense GL distribution {start.isoformat()} to "
            f"{finish.isoformat()}; signed net debit-minus-credit, "
            "negative reversal net allowed; shares N/A for zero/negative total; "
            "not bank cash spend or cash-basis expense"
        ),
        filename=f"expense-gl-distribution-{start.isoformat()}-{finish.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
