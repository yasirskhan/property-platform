"""Posted journal-entry register; no GL mutation, settlement, or inferred allocations.

Only recorded JOURNAL_ENTRY transactions and reversals pointing to same-org
JOURNAL_ENTRY originals are eligible. A reversed original and its reversal
both remain visible, with clear markers. Other transaction sources omitted.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _bool_param, _date_param, _int_param,
)

HEADERS = (
    "Posted Date", "GL Transaction ID", "GL Entry ID",
    "Recorded Transaction Type", "Original Journal ID", "Reversal State",
    "Recorded Reference", "Recorded Source Type",
    "GL Number", "GL Account", "Recorded Entry Description",
    "Posted Debit", "Posted Credit",
)


def build_journal_entry_register(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"date_from", "date_to", "transaction_id", "include_reversals"}:
        raise ReportDeliveryError("Unsupported Journal Entry Register parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Journal Entry Register permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.JOURNAL_ENTRIES", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Journal Entry Register permission required")
    start = _date_param(parameters, "date_from")
    finish = _date_param(parameters, "date_to")
    if start is None or finish is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > finish:
        raise ReportDeliveryError("date_from cannot be after date_to")
    target_id = _int_param(parameters, "transaction_id")
    include_reversals = _bool_param(parameters, "include_reversals", True)

    original = aliased(GLTransaction)
    query = db.query(GLTransaction).outerjoin(
        original, original.id == GLTransaction.reversal_of_id,
    ).filter(
        GLTransaction.organization_id == organization_id,
        GLTransaction.transaction_date >= start,
        GLTransaction.transaction_date <= finish,
        or_(
            GLTransaction.transaction_type == "JOURNAL_ENTRY",
            and_(
                GLTransaction.transaction_type == "REVERSAL",
                original.organization_id == organization_id,
                original.transaction_type == "JOURNAL_ENTRY",
            ),
        ),
    )
    if not include_reversals:
        query = query.filter(GLTransaction.transaction_type == "JOURNAL_ENTRY")
    if target_id is not None:
        if query.filter(GLTransaction.id == target_id).first() is None:
            raise ReportDeliveryError("Journal transaction not found")
        query = query.filter(GLTransaction.id == target_id)

    transactions = query.order_by(
        GLTransaction.transaction_date.asc(), GLTransaction.id.asc(),
    ).limit(5001).all()
    if len(transactions) > 5000:
        raise ReportDeliveryError("Narrow Journal Entry Register filters before exporting")
    ids = [txn.id for txn in transactions]
    lines = (
        db.query(GLEntry, GLAccount).join(
            GLAccount, GLAccount.id == GLEntry.gl_account_id,
        ).filter(GLEntry.transaction_id.in_(ids)).order_by(
            GLEntry.transaction_id.asc(), GLEntry.id.asc(),
        ).limit(5001).all()
        if ids else []
    )
    if len(lines) > 5000:
        raise ReportDeliveryError("Narrow Journal Entry Register filters before exporting")

    by_transaction: dict[int, list[tuple[GLEntry, GLAccount]]] = defaultdict(list)
    for entry, account in lines:
        if entry.organization_id != organization_id or account.organization_id != organization_id:
            raise ReportDeliveryError("Journal entry organization requires review")
        by_transaction[entry.transaction_id].append((entry, account))

    rows: list[tuple[object, ...]] = []
    total_debit = total_credit = Decimal("0")
    for txn in transactions:
        txn_lines = by_transaction.get(txn.id, [])
        if len(txn_lines) < 2:
            raise ReportDeliveryError("Journal transaction lines require review")
        txn_debit = txn_credit = Decimal("0")
        state = (
            f"REVERSAL OF {txn.reversal_of_id}"
            if txn.transaction_type == "REVERSAL"
            else "REVERSED" if txn.is_reversed else "ORIGINAL"
        )
        for entry, account in txn_lines:
            debit, credit = Decimal(entry.debit or 0), Decimal(entry.credit or 0)
            if debit < 0 or credit < 0 or (debit == 0 and credit == 0) or (debit > 0 and credit > 0):
                raise ReportDeliveryError("Journal line debit/credit requires review")
            txn_debit += debit
            txn_credit += credit
            rows.append((
                txn.transaction_date, txn.id, entry.id,
                txn.transaction_type, txn.reversal_of_id or "", state,
                txn.reference_number or "", txn.source_type or "",
                account.gl_number, account.name, entry.description or "",
                debit, credit,
            ))
        if txn_debit != txn_credit or txn_debit <= 0:
            raise ReportDeliveryError("Unbalanced journal transaction requires review")
        total_debit += txn_debit
        total_credit += txn_credit
    rows.append((
        "", "", "", "", "", "", "TOTAL", "", "", "",
        "", total_debit, total_credit,
    ))
    return ReportPayload(
        title=(
            f"Posted Journal Entry Register {start.isoformat()} to {finish.isoformat()}; "
            "original journals and linked reversals, each balanced; "
            "recorded GL book entries, NOT bank clearing or a reconstructed historic snapshot. "
            "CASH/ACCRUAL display toggle does not alter posted GL."
        ),
        filename=f"posted-journal-entry-register-{start.isoformat()}-{finish.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
