from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.owner_payout import OwnerPayout
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.owner_payout import (
    OwnerPayoutCandidateOut,
    OwnerPayoutConfirmIn,
    OwnerPayoutConfirmOut,
    OwnerPayoutDraftIn,
    OwnerPayoutDraftOut,
    OwnerPayoutListOut,
    OwnerPayoutOut,
    OwnerPayoutPreviewOut,
)
from app.services.customer_features import resolve_customer_features
from app.services.owner_payout_confirmation import confirm_external_payout_batch
from app.services.owner_payouts import (
    OwnerPayoutError,
    create_owner_payout_draft,
    list_owner_payouts,
    preview_owner_payouts,
)

router = APIRouter(
    prefix="/api/accounting/owner-payouts",
    tags=["Owner Payouts"],
)

FEATURE_KEY = "release.accounting.pay_owners"
WRITE_ROLES = {"ADMIN", "MANAGER"}


def _role_value(role) -> str:
    return (role.value if hasattr(role, "value") else str(role or "")).upper()


def _require_write(user: User) -> None:
    if _role_value(user.role) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and managers may prepare owner payouts.",
        )


def _require_feature(db: Session, user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=user)
            if item.key == FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pay Owners is not enabled.",
        )
    return user.organization_id


def _out(row: OwnerPayout) -> OwnerPayoutOut:
    owner_name = (
        getattr(row.owner, "full_name", None)
        if row.owner is not None
        else None
    )
    owner_email = row.owner.email if row.owner is not None else ""
    return OwnerPayoutOut(
        id=row.id,
        batch_reference=row.batch_reference,
        owner_id=row.owner_id,
        owner_name=owner_name or owner_email or f"Owner #{row.owner_id}",
        owner_email=owner_email,
        bank_account_id=row.bank_account_id,
        bank_account_name=(
            row.bank_account.name if row.bank_account is not None else ""
        ),
        effective_date=row.effective_date,
        amount=row.amount,
        destination_last4=row.destination_last4,
        status=row.status,
        gl_transaction_id=row.gl_transaction_id,
        created_by_id=row.created_by_id,
        confirmed_by_id=row.confirmed_by_id,
        created_at=row.created_at,
        confirmed_at=row.confirmed_at,
    )


@router.get("/preview", response_model=OwnerPayoutPreviewOut)
def preview(
    bank_account_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_feature(db, current_user)
    try:
        result = preview_owner_payouts(
            db,
            organization_id=organization_id,
            bank_account_id=bank_account_id,
        )
    except OwnerPayoutError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OwnerPayoutPreviewOut(
        bank_account_id=result["bank_account_id"],
        bank_account_name=result["bank_account_name"],
        book_balance=result["book_balance"],
        candidates=[
            OwnerPayoutCandidateOut(**item) for item in result["candidates"]
        ],
    )


@router.post("/draft", response_model=OwnerPayoutDraftOut, status_code=201)
def create_draft(
    payload: OwnerPayoutDraftIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_feature(db, current_user)
    try:
        batch_reference, total, rows = create_owner_payout_draft(
            db,
            organization_id=organization_id,
            payload=payload,
            created_by=current_user,
        )
    except OwnerPayoutError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refreshed = list_owner_payouts(
        db,
        organization_id=organization_id,
        limit=max(len(rows), 1) + 20,
    )
    by_id = {row.id: row for row in refreshed}
    return OwnerPayoutDraftOut(
        batch_reference=batch_reference,
        entry_count=len(rows),
        total_amount=total,
        funds_moved=False,
        accounting_posted=False,
        payouts=[_out(by_id.get(row.id, row)) for row in rows],
    )


@router.post(
    "/{batch_reference}/confirm-external-payment",
    response_model=OwnerPayoutConfirmOut,
)
def confirm_external_payment(
    batch_reference: str,
    payload: OwnerPayoutConfirmIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_feature(db, current_user)
    try:
        rows = confirm_external_payout_batch(
            db,
            organization_id=organization_id,
            batch_reference=batch_reference,
            confirmation_date=payload.confirmation_date,
            confirmed_by=current_user,
        )
    except OwnerPayoutError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refreshed = list_owner_payouts(
        db,
        organization_id=organization_id,
        limit=max(len(rows), 1) + 20,
    )
    by_id = {row.id: row for row in refreshed}
    total = sum((Decimal(row.amount or 0) for row in rows), Decimal("0.00"))
    return OwnerPayoutConfirmOut(
        batch_reference=batch_reference,
        entry_count=len(rows),
        total_amount=total,
        funds_moved_by_app=False,
        externally_confirmed=True,
        accounting_posted=True,
        payouts=[_out(by_id.get(row.id, row)) for row in rows],
    )


@router.get("", response_model=OwnerPayoutListOut)
def history(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_feature(db, current_user)
    rows = list_owner_payouts(
        db,
        organization_id=organization_id,
        limit=limit,
    )
    return OwnerPayoutListOut(items=[_out(row) for row in rows], total=len(rows))
