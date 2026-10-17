"""Ledger-native bank adjustments.

Bank adjustments are ordinary immutable GL transactions with a dedicated
transaction type and source metadata. No duplicate bank-adjustment table is
needed, and reconciliation can discover them from the bank GL line.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import PostingError, post_transaction, reverse_transaction

CENT = Decimal("0.01")
SOURCE_TYPE = "bank_adjustment"
TRANSACTION_TYPE = "BANK_ADJUSTMENT"


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT)


def _offset_account(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    offset_gl_account_id: int,
) -> GLAccount:
    account = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == offset_gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
        )
        .first()
    )
    if account is None:
        raise PostingError("Offset GL account not found in your organization.")
    if account.id == bank_account.gl_account_id:
        raise PostingError("Offset GL account must differ from the bank GL account.")
    return account


def list_bank_adjustments(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    limit: int = 500,
) -> list[GLTransaction]:
    return (
        db.query(GLTransaction)
        .options(joinedload(GLTransaction.entries).joinedload(GLEntry.gl_account))
        .filter(
            GLTransaction.organization_id == organization_id,
            GLTransaction.transaction_type == TRANSACTION_TYPE,
            GLTransaction.source_type == SOURCE_TYPE,
            GLTransaction.source_id == bank_account.id,
        )
        .order_by(GLTransaction.transaction_date.desc(), GLTransaction.id.desc())
        .limit(limit)
        .all()
    )


def get_bank_adjustment(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    transaction_id: int,
) -> GLTransaction:
    row = (
        db.query(GLTransaction)
        .options(joinedload(GLTransaction.entries).joinedload(GLEntry.gl_account))
        .filter(
            GLTransaction.id == transaction_id,
            GLTransaction.organization_id == organization_id,
            GLTransaction.transaction_type == TRANSACTION_TYPE,
            GLTransaction.source_type == SOURCE_TYPE,
            GLTransaction.source_id == bank_account.id,
        )
        .first()
    )
    if row is None:
        raise PostingError("Bank adjustment not found.")
    return row


def create_bank_adjustment(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    adjustment_date: date,
    direction: str,
    amount: Decimal,
    offset_gl_account_id: int,
    created_by: User,
    reference_number: str | None = None,
    memo: str | None = None,
) -> GLTransaction:
    if bank_account.organization_id != organization_id or not bank_account.is_active:
        raise PostingError("Bank account not found in your organization.")

    offset = _offset_account(
        db,
        organization_id=organization_id,
        bank_account=bank_account,
        offset_gl_account_id=offset_gl_account_id,
    )
    normalized_amount = _money(amount)
    if normalized_amount <= 0:
        raise PostingError("Adjustment amount must be greater than zero.")

    normalized_direction = str(direction or "").upper()
    description = memo or f"Bank adjustment {normalized_direction.lower()}"
    if normalized_direction == "INCREASE":
        lines = [
            PostingLine(
                gl_account_id=bank_account.gl_account_id,
                description=description,
                debit=normalized_amount,
            ),
            PostingLine(
                gl_account_id=offset.id,
                description=description,
                credit=normalized_amount,
            ),
        ]
    elif normalized_direction == "DECREASE":
        lines = [
            PostingLine(
                gl_account_id=offset.id,
                description=description,
                debit=normalized_amount,
            ),
            PostingLine(
                gl_account_id=bank_account.gl_account_id,
                description=description,
                credit=normalized_amount,
            ),
        ]
    else:
        raise PostingError("Direction must be INCREASE or DECREASE.")

    transaction = post_transaction(
        db=db,
        organization_id=organization_id,
        transaction_date=adjustment_date,
        transaction_type=TRANSACTION_TYPE,
        memo=memo,
        lines=lines,
        created_by=created_by,
        reference_number=reference_number,
        source_type=SOURCE_TYPE,
        source_id=bank_account.id,
    )
    return get_bank_adjustment(
        db,
        organization_id=organization_id,
        bank_account=bank_account,
        transaction_id=transaction.id,
    )


def reverse_bank_adjustment(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    transaction_id: int,
    reversal_date: date,
    created_by: User,
    memo: str | None = None,
) -> GLTransaction:
    original = get_bank_adjustment(
        db,
        organization_id=organization_id,
        bank_account=bank_account,
        transaction_id=transaction_id,
    )
    reverse_transaction(
        db,
        original=original,
        reversal_date=reversal_date,
        created_by=created_by,
        memo=memo,
    )
    return get_bank_adjustment(
        db,
        organization_id=organization_id,
        bank_account=bank_account,
        transaction_id=transaction_id,
    )
