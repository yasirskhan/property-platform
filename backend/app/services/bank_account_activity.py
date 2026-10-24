"""Read-only dated posted GL cash-book activity for one bank-account mapping.

Not external statement activity, cleared checks, bank-feed inbox, bank
reconciliation, or settlement history. Sensitive BankAccount routing and
account numbers must never leave this service.
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
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)
from app.services.reporting_basis import get_accounting_basis

HEADERS = (
    "Posted Date", "Transaction ID", "Transaction Type",
    "Recorded Reference", "Posted Debit", "Posted Credit",
    "Running GL Book Balance",
)


def build_bank_account_activity(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"bank_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported bank activity parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Bank activity permission required")
    for key in (
        "REPORTING.ALL", "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.GL_ACCOUNTS",
    ):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Bank activity permission required")
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError(
            "Posted GL bank book activity uses ACCRUAL basis; CASH presentation is not available"
        )
    bank_id = _int_param(parameters, "bank_id", required=True)
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from and date_to and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    bank = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == bank_id,
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
            BankAccount.deleted_at.is_(None),
        )
        .first()
    )
    if bank is None:
        raise ReportDeliveryError("Bank account not found")
    cash_account = db.query(GLAccount).filter(
        GLAccount.id == bank.gl_account_id,
        GLAccount.organization_id == organization_id,
        GLAccount.account_type == "ASSET",
    ).first()
    if cash_account is None:
        raise ReportDeliveryError("Linked cash GL account not found")

    entries = db.query(GLEntry, GLTransaction).join(
        GLTransaction, GLTransaction.id == GLEntry.transaction_id,
    ).filter(
        GLEntry.organization_id == organization_id,
        GLTransaction.organization_id == organization_id,
        GLEntry.gl_account_id == cash_account.id,
    )
    opening = Decimal("0")
    if date_from is not None:
        debit, credit = (
            db.query(
                func.coalesce(func.sum(GLEntry.debit), 0),
                func.coalesce(func.sum(GLEntry.credit), 0),
            ).join(
                GLTransaction, GLTransaction.id == GLEntry.transaction_id,
            ).filter(
                GLEntry.organization_id == organization_id,
                GLTransaction.organization_id == organization_id,
                GLEntry.gl_account_id == cash_account.id,
                GLTransaction.transaction_date < date_from,
            ).one()
        )
        opening = Decimal(debit or 0) - Decimal(credit or 0)
        entries = entries.filter(GLTransaction.transaction_date >= date_from)
    if date_to is not None:
        entries = entries.filter(GLTransaction.transaction_date <= date_to)
    running = opening
    rows = [("OPENING", "", "", "", "", "", opening)]
    for entry, tx in entries.order_by(
        GLTransaction.transaction_date.asc(),
        GLTransaction.id.asc(), GLEntry.id.asc(),
    ).all():
        debit = Decimal(entry.debit or 0)
        credit = Decimal(entry.credit or 0)
        running += debit - credit
        rows.append((
            tx.transaction_date, tx.id, tx.transaction_type,
            tx.reference_number or "", debit, credit, running,
        ))
    label_from = date_from.isoformat() if date_from else "beginning"
    label_to = date_to.isoformat() if date_to else "latest"
    return ReportPayload(
        title=(
            f"Posted GL bank book: {cash_account.gl_number} ({bank.name}), "
            f"{label_from} to {label_to}; not cleared bank activity"
        ),
        filename=f"bank-book-activity-{bank.id}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
