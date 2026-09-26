"""Bank Feed import API for the Phase 3.6 provider-neutral inbox."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.bank_feed import BankFeedTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.bank_feed import (
    BankFeedImportIn,
    BankFeedImportOut,
    BankFeedListOut,
    BankFeedRematchOut,
    BankFeedTransactionOut,
)
from app.services.bank_feed import BankFeedError, import_bank_feed_csv, rematch_bank_feed
from app.services.customer_features import resolve_customer_features

router = APIRouter(
    prefix="/api/accounting/bank-accounts",
    tags=["Bank Feed"],
)

FEATURE_KEY = "release.accounting.bank_feed"


def _require_feature(db: Session, current_user: User) -> int:
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
            detail="Bank Feed capability is not enabled.",
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


def _out(row: BankFeedTransaction) -> BankFeedTransactionOut:
    return BankFeedTransactionOut(
        id=row.id,
        bank_account_id=row.bank_account_id,
        posted_date=row.posted_date,
        amount=row.amount,
        payee=row.payee,
        description=row.description,
        memo=row.memo,
        reference_number=row.reference_number,
        source_provider=row.source_provider,
        external_id=row.external_id,
        status=row.status,
        matched_source_type=row.matched_source_type,
        matched_source_id=row.matched_source_id,
        created_at=row.created_at,
    )


@router.get("/{bank_account_id}/bank-feed", response_model=BankFeedListOut)
def list_bank_feed(
    bank_account_id: int,
    status_filter: Optional[str] = Query(None, pattern="^(MATCHED|UNMATCHED)$"),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_feature(db, current_user)
    _bank(db, organization_id, bank_account_id)
    query = db.query(BankFeedTransaction).filter(
        BankFeedTransaction.organization_id == organization_id,
        BankFeedTransaction.bank_account_id == bank_account_id,
    )
    if status_filter is not None:
        query = query.filter(BankFeedTransaction.status == status_filter)
    total = query.count()
    rows = (
        query.order_by(
            BankFeedTransaction.posted_date.desc(),
            BankFeedTransaction.id.desc(),
        )
        .limit(limit)
        .all()
    )
    return BankFeedListOut(items=[_out(row) for row in rows], total=total)


@router.post(
    "/{bank_account_id}/bank-feed/import",
    response_model=BankFeedImportOut,
)
def import_bank_feed(
    bank_account_id: int,
    payload: BankFeedImportIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_feature(db, current_user)
    bank_account = _bank(db, organization_id, bank_account_id)
    try:
        imported, duplicates, matched, total = import_bank_feed_csv(
            db,
            organization_id=organization_id,
            bank_account=bank_account,
            content=payload.content,
            created_by=current_user,
        )
    except BankFeedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return BankFeedImportOut(
        imported=imported,
        duplicates=duplicates,
        matched=matched,
        total=total,
    )


@router.post(
    "/{bank_account_id}/bank-feed/rematch",
    response_model=BankFeedRematchOut,
)
def rematch_bank_feed_route(
    bank_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_feature(db, current_user)
    bank_account = _bank(db, organization_id, bank_account_id)
    try:
        matched, remaining = rematch_bank_feed(
            db,
            organization_id=organization_id,
            bank_account=bank_account,
        )
    except BankFeedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return BankFeedRematchOut(matched=matched, remaining_unmatched=remaining)
