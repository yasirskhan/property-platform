"""Customer workflow for Owner Held Security Deposit Key Accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.owner_held_deposit import (
    DepositGLAccountOut,
    DepositKeyAccountIn,
    DepositKeyAccountOut,
    OwnerHeldDepositSetupOut,
)
from app.services.owner_held_deposits import (
    OwnerHeldDepositError,
    add_deposit_key_account,
    list_deposit_key_accounts,
    list_eligible_deposit_accounts,
    operating_cash_account,
    owner_held_feature_allowed,
    remove_deposit_key_account,
)

router = APIRouter(
    prefix="/api/accounting/owner-held-security-deposits",
    tags=["Owner Held Security Deposits"],
)

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}


def _role(user: User) -> str:
    value = getattr(user.role, "value", user.role)
    return str(value or "").upper()


def _require_capability(db: Session, current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    if not owner_held_feature_allowed(db, user=current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner Held Security Deposits capability is not enabled.",
        )
    return current_user.organization_id


def _require_write(current_user: User) -> None:
    if _role(current_user) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN, OWNER, or MANAGER can manage deposit Key Accounts.",
        )


def _key_out(row) -> DepositKeyAccountOut:
    account = row.gl_account
    return DepositKeyAccountOut(
        id=row.id,
        organization_id=row.organization_id,
        gl_account_id=account.id,
        gl_number=account.gl_number,
        name=account.name,
        offset_account=account.offset_account,
        created_at=row.created_at,
    )


def _gl_out(account) -> DepositGLAccountOut:
    return DepositGLAccountOut(
        gl_account_id=account.id,
        gl_number=account.gl_number,
        name=account.name,
        offset_account=account.offset_account,
    )


@router.get("", response_model=OwnerHeldDepositSetupOut)
def get_owner_held_deposit_setup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_capability(db, current_user)
    operating = operating_cash_account(db, organization_id=organization_id)
    configured = list_deposit_key_accounts(db, organization_id=organization_id)
    eligible = list_eligible_deposit_accounts(db, organization_id=organization_id)
    return OwnerHeldDepositSetupOut(
        operating_cash_gl_number=operating.gl_number,
        key_accounts=[_key_out(row) for row in configured],
        eligible_accounts=[_gl_out(account) for account in eligible],
    )


@router.post(
    "/key-accounts",
    response_model=DepositKeyAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def create_deposit_key_account(
    payload: DepositKeyAccountIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_capability(db, current_user)
    try:
        row = add_deposit_key_account(
            db,
            organization_id=organization_id,
            gl_account_id=payload.gl_account_id,
            created_by=current_user,
        )
    except OwnerHeldDepositError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _key_out(row)


@router.delete("/key-accounts/{key_account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deposit_key_account(
    key_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_capability(db, current_user)
    try:
        remove_deposit_key_account(
            db,
            organization_id=organization_id,
            key_account_id=key_account_id,
        )
    except OwnerHeldDepositError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return None
