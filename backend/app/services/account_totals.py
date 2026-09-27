"""Read-only posted accrual GL account totals, including genuine reversals.

No ledger edits, implicit cash-basis transformation or historical
reconstruction from editable summary fields. Net is DEBIT minus CREDIT
for every account type; not a normalized financial-statement balance.
"""
from __future__ import annotations

from datetime import date
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

HEADERS = ("GL Number", "Account Name", "Account Type", "Posted Debit",
           "Posted Credit", "Net Debit Minus Credit")


def build_account_totals(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"as_of", "include_zero"}:
        raise ReportDeliveryError("Unsupported account totals parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Account totals permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Account totals permission required")
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError(
            "Account totals use posted ACCRUAL GL; CASH-basis account totals are not available"
        )
    as_of = _date_param(parameters, "as_of")
    include_zero = _bool_param(parameters, "include_zero", False)
    entries = db.query(
        GLEntry.gl_account_id,
        func.coalesce(func.sum(GLEntry.debit), 0).label("debit"),
        func.coalesce(func.sum(GLEntry.credit), 0).label("credit"),
    ).join(
        GLTransaction, GLTransaction.id == GLEntry.transaction_id,
    ).filter(
        GLEntry.organization_id == organization_id,
        GLTransaction.organization_id == organization_id,
    )
    if as_of is not None:
        entries = entries.filter(GLTransaction.transaction_date <= as_of)
    totals = {
        row.gl_account_id: (Decimal(row.debit or 0), Decimal(row.credit or 0))
        for row in entries.group_by(GLEntry.gl_account_id).all()
    }
    # Preserve real entries on inactive/archived accounts: hiding
    # their activity would distort financial totals.
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == organization_id,
    ).order_by(GLAccount.gl_number.asc(), GLAccount.id.asc()).all()
    rows = []
    for account in accounts:
        debit, credit = totals.get(account.id, (Decimal("0"), Decimal("0")))
        if not include_zero and debit == 0 and credit == 0:
            continue
        rows.append((
            account.gl_number, account.name, account.account_type,
            debit, credit, debit - credit,
        ))
    label = as_of.isoformat() if as_of is not None else "all-recorded-dates"
    return ReportPayload(
        title=f"Posted accrual GL account totals through {label} (net = debit minus credit)",
        filename=f"account-totals-{label}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
