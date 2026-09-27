"""Read-only deposit register. A deposit only groups already-posted receipts.

Deposit does not move cash in the GL or prove bank deposit settlement.
Never expose account/routing numbers or create inferred bank payments.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.receipt import Receipt
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)

HEADERS = (
    "Deposit ID", "Recorded Deposit Date", "Recorded Deposit Number",
    "Recorded Cash GL Number", "Recorded Cash GL Name",
    "Recorded Grouping Total", "Receipt Count", "Reversed Receipt Count",
    "Recorded Description", "Receipt Grouping Status",
)
CENT = Decimal("0.01")


def build_deposit_register(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"deposit_id", "bank_gl_account_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported Deposit Register parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Deposit Register permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.DEPOSITS", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Deposit Register permission required")
    deposit_id = _int_param(parameters, "deposit_id")
    gl_id = _int_param(parameters, "bank_gl_account_id")
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    if gl_id is not None and db.query(GLAccount.id).filter(
        GLAccount.id == gl_id, GLAccount.organization_id == organization_id,
        GLAccount.account_type == "ASSET",
    ).first() is None:
        raise ReportDeliveryError("Deposit cash GL account not found")
    query = db.query(Deposit).filter(
        Deposit.organization_id == organization_id,
        Deposit.is_active.is_(True), Deposit.deleted_at.is_(None),
    )
    if deposit_id is not None:
        query = query.filter(Deposit.id == deposit_id)
    if gl_id is not None:
        query = query.filter(Deposit.bank_gl_account_id == gl_id)
    if date_from is not None:
        query = query.filter(Deposit.deposit_date >= date_from)
    if date_to is not None:
        query = query.filter(Deposit.deposit_date <= date_to)
    deposits = query.order_by(Deposit.deposit_date.asc(), Deposit.id.asc()).limit(5001).all()
    if len(deposits) > 5000:
        raise ReportDeliveryError("Narrow Deposit Register filters before exporting")
    if deposit_id is not None and not deposits:
        raise ReportDeliveryError("Deposit not found")

    rows: list[tuple[object, ...]] = []
    for deposit in deposits:
        account = db.query(GLAccount).filter(
            GLAccount.id == deposit.bank_gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "ASSET",
        ).first()
        if account is None:
            raise ReportDeliveryError("Deposit cash GL account mapping needs review")
        lines = db.query(DepositLine).filter(
            DepositLine.deposit_id == deposit.id,
        ).order_by(DepositLine.id.asc()).all()
        if not lines:
            raise ReportDeliveryError("Deposit has no recorded receipts")
        count = reversed_count = 0
        receipt_ids: set[int] = set()
        total = Decimal("0")
        for line in lines:
            if line.organization_id != organization_id or line.receipt_id in receipt_ids:
                raise ReportDeliveryError("Deposit line organization or receipt needs review")
            receipt_ids.add(line.receipt_id)
            receipt = db.query(Receipt).filter(
                Receipt.id == line.receipt_id,
                Receipt.organization_id == organization_id,
            ).first()
            if receipt is None:
                raise ReportDeliveryError("Deposit receipt organization needs review")
            if receipt.cash_gl_account_id != account.id:
                raise ReportDeliveryError("Deposit receipt cash GL mapping needs review")
            posting = db.query(GLTransaction).filter(
                GLTransaction.id == receipt.gl_transaction_id,
                GLTransaction.organization_id == organization_id,
                GLTransaction.transaction_type == "RECEIPT",
                GLTransaction.source_type == "receipt",
                GLTransaction.source_id == receipt.id,
            ).first()
            if posting is None or bool(posting.is_reversed) != bool(receipt.is_reversed):
                raise ReportDeliveryError("Deposit receipt original GL posting needs review")
            amount = Decimal(receipt.amount or 0)
            if amount <= 0 or amount.as_tuple().exponent < -2:
                raise ReportDeliveryError("Invalid recorded deposit receipt amount")
            total += amount
            count += 1
            if receipt.is_reversed:
                reversed_count += 1
        recorded = Decimal(deposit.total or 0)
        if recorded <= 0 or recorded.quantize(CENT) != total.quantize(CENT):
            raise ReportDeliveryError("Deposit and receipt grouping totals disagree")
        rows.append((
            deposit.id, deposit.deposit_date, deposit.deposit_number or "",
            account.gl_number, account.name, recorded, count, reversed_count,
            deposit.description or "",
            "REVERSED RECEIPTS PRESENT" if reversed_count else "RECORDED GROUPING ONLY",
        ))
    return ReportPayload(
        title=(
            "Recorded deposit/receipt groupings; NOT a new GL cash posting, "
            "bank-cleared deposit or reconciled bank balance"
        ),
        filename="recorded-deposit-register.csv",
        headers=HEADERS, rows=tuple(rows),
    )
