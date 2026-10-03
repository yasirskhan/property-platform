"""Customer-facing Bank Adjustments workflow."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.bank_adjustment import (
    BankAdjustmentCreateIn,
    BankAdjustmentListOut,
    BankAdjustmentOut,
    BankAdjustmentReverseIn,
)
from app.services.bank_adjustments import (
    create_bank_adjustment,
    list_bank_adjustments,
    reverse_bank_adjustment,
)
from app.services.customer_features import resolve_customer_features
from app.services.gl_posting import PostingError

router = APIRouter(
    prefix="/api/accounting/bank-accounts",
    tags=["Bank Adjustments"],
)

FEATURE_KEY = "release.accounting.bank_adjustments"


def _require_adjustments_capability(db: Session, current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bank Adjustments capability is not enabled.",
        )
    return current_user.organization_id


def _bank(db: Session, organization_id: int, bank_account_id: int) -> BankAccount:
    row = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found.",
        )
    return row


def _to_out(transaction: GLTransaction, bank_account: BankAccount) -> BankAdjustmentOut:
    bank_entry = next(
        (
            entry
            for entry in transaction.entries
            if entry.gl_account_id == bank_account.gl_account_id
        ),
        None,
    )
    offset_entry = next(
        (
            entry
            for entry in transaction.entries
            if entry.gl_account_id != bank_account.gl_account_id
        ),
        None,
    )
    if bank_entry is None or offset_entry is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bank adjustment ledger lines are incomplete.",
        )

    signed_amount = Decimal(bank_entry.debit or 0) - Decimal(bank_entry.credit or 0)
    direction = "INCREASE" if signed_amount > 0 else "DECREASE"
    return BankAdjustmentOut(
        id=transaction.id,
        bank_account_id=bank_account.id,
        bank_account_name=bank_account.name,
        transaction_date=transaction.transaction_date,
        posted_at=transaction.posted_at,
        direction=direction,
        amount=abs(signed_amount),
        signed_amount=signed_amount,
        offset_gl_account_id=offset_entry.gl_account_id,
        offset_gl_account_number=(
            offset_entry.gl_account.gl_number if offset_entry.gl_account else None
        ),
        offset_gl_account_name=(
            offset_entry.gl_account.name if offset_entry.gl_account else None
        ),
        reference_number=transaction.reference_number,
        memo=transaction.memo,
        is_reversed=transaction.is_reversed,
        created_by_id=transaction.created_by_id,
    )


@router.get(
    "/{bank_account_id}/adjustments",
    response_model=BankAdjustmentListOut,
)
def get_bank_adjustments(
    bank_account_id: int,
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_adjustments_capability(db, current_user)
    bank_account = _bank(db, organization_id, bank_account_id)
    rows = list_bank_adjustments(
        db,
        organization_id=organization_id,
        bank_account=bank_account,
        limit=limit,
    )
    return BankAdjustmentListOut(
        items=[_to_out(row, bank_account) for row in rows],
        total=len(rows),
    )


@router.post(
    "/{bank_account_id}/adjustments",
    response_model=BankAdjustmentOut,
    status_code=status.HTTP_201_CREATED,
)
def post_bank_adjustment(
    bank_account_id: int,
    payload: BankAdjustmentCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_adjustments_capability(db, current_user)
    bank_account = _bank(db, organization_id, bank_account_id)
    try:
        row = create_bank_adjustment(
            db,
            organization_id=organization_id,
            bank_account=bank_account,
            adjustment_date=payload.adjustment_date,
            direction=payload.direction,
            amount=payload.amount,
            offset_gl_account_id=payload.offset_gl_account_id,
            reference_number=payload.reference_number,
            memo=payload.memo,
            created_by=current_user,
        )
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _to_out(row, bank_account)


@router.post(
    "/{bank_account_id}/adjustments/{transaction_id}/reverse",
    response_model=BankAdjustmentOut,
)
def reverse_bank_adjustment_route(
    bank_account_id: int,
    transaction_id: int,
    payload: BankAdjustmentReverseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_adjustments_capability(db, current_user)
    bank_account = _bank(db, organization_id, bank_account_id)
    try:
        row = reverse_bank_adjustment(
            db,
            organization_id=organization_id,
            bank_account=bank_account,
            transaction_id=transaction_id,
            reversal_date=payload.reversal_date,
            memo=payload.memo,
            created_by=current_user,
        )
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _to_out(row, bank_account)
