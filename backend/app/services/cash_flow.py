"""Read-only posted GL bank-mapped cash movements (not a GAAP cash flow statement).

Opening/ending figures include ONLY mapped organization ASSET GL accounts with
include_on_cash_flow=True. Cash account-to-account transfers count in BOTH
gross debit/credit columns and cancel in NET. No unverified classification,
bank feed, clearing, bank account/routing numbers or accounting mutations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param

HEADERS = (
    "Bank ID", "Bank Display Name", "GL Number",
    "Opening Posted Book Cash", "Posted Debits / Inflows",
    "Posted Credits / Outflows", "Net Book Cash Movement",
    "Ending Posted Book Cash",
)


def _account_totals(
    db: Session, *, organization_id: int, gl_ids: tuple[int, ...],
    date_from=None, date_to=None, before_date=None,
) -> dict[int, tuple[Decimal, Decimal]]:
    if not gl_ids:
        return {}
    entries = db.query(
        GLEntry.gl_account_id,
        func.coalesce(func.sum(GLEntry.debit), 0),
        func.coalesce(func.sum(GLEntry.credit), 0),
    ).join(
        GLTransaction, GLTransaction.id == GLEntry.transaction_id,
    ).filter(
        GLEntry.organization_id == organization_id,
        GLTransaction.organization_id == organization_id,
        GLEntry.gl_account_id.in_(gl_ids),
    )
    if date_from is not None:
        entries = entries.filter(GLTransaction.transaction_date >= date_from)
    if date_to is not None:
        entries = entries.filter(GLTransaction.transaction_date <= date_to)
    if before_date is not None:
        entries = entries.filter(GLTransaction.transaction_date < before_date)
    return {
        int(account_id): (Decimal(debit or 0), Decimal(credit or 0))
        for account_id, debit, credit in entries.group_by(GLEntry.gl_account_id).all()
    }


def build_cash_flow(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported cash flow parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Cash flow permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Cash flow permission required")

    start = _date_param(parameters, "date_from")
    finish = _date_param(parameters, "date_to")
    if start is None or finish is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > finish:
        raise ReportDeliveryError("date_from cannot be after date_to")

    # Include archived banks and archived GL accounts: excluding past
    # posted cash movements would falsify historical book-cash movement.
    banks = db.query(BankAccount).filter(
        BankAccount.organization_id == organization_id,
    ).order_by(BankAccount.name.asc(), BankAccount.id.asc()).all()
    cash_banks = []
    for bank in banks:
        gl = db.query(GLAccount).filter(
            GLAccount.id == bank.gl_account_id,
            GLAccount.organization_id == organization_id,
        ).first()
        if gl is None or gl.account_type != "ASSET":
            raise ReportDeliveryError("Bank-to-GL cash account mapping needs review")
        if gl.include_on_cash_flow:
            cash_banks.append((bank, gl))

    gl_ids = tuple(gl.id for _, gl in cash_banks)
    opening = _account_totals(
        db, organization_id=organization_id, gl_ids=gl_ids,
        before_date=start,
    )
    period = _account_totals(
        db, organization_id=organization_id, gl_ids=gl_ids,
        date_from=start, date_to=finish,
    )
    rows = []
    total_open = total_in = total_out = total_close = Decimal("0")
    for bank, gl in cash_banks:
        old_dr, old_cr = opening.get(gl.id, (Decimal("0"), Decimal("0")))
        dr, cr = period.get(gl.id, (Decimal("0"), Decimal("0")))
        first = old_dr - old_cr
        last = first + dr - cr
        total_open += first
        total_in += dr
        total_out += cr
        total_close += last
        rows.append((
            bank.id, bank.name, gl.gl_number, first, dr, cr, dr - cr, last,
        ))
    rows.append((
        "TOTAL", "Configured bank-mapped GL cash", "",
        total_open, total_in, total_out, total_in - total_out, total_close,
    ))
    return ReportPayload(
        title=(
            f"Posted GL bank-mapped book cash movement {start.isoformat()} to "
            f"{finish.isoformat()}; not a classified cash flow statement, "
            "not cleared bank balance; internal transfers inflate gross movements; "
            "unmapped or excluded cash accounts not included"
        ),
        filename=f"cash-book-movement-{start.isoformat()}-{finish.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
