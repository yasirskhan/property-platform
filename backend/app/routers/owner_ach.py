from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.owner_ach import OwnerACHAccount
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.ach_file import ACHTestFileIn, ACHTestFileOut
from app.schemas.owner_ach import OwnerACHOut, OwnerACHUpsertIn
from app.services.ach_file import ACHFileError, generate_ach_test_file
from app.services.customer_features import resolve_customer_features
from app.services.owner_ach import OwnerACHError, get_owner_ach, upsert_owner_ach

router = APIRouter(
    prefix="/api/accounting/owners",
    tags=["Owner ACH"],
)

FEATURE_KEY = "release.accounting.owner_ach_setup"
WRITE_ROLES = {"ADMIN", "OWNER"}


def _role_value(role) -> str:
    return (role.value if hasattr(role, "value") else str(role or "")).upper()


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
            detail="Owner ACH Setup is not enabled.",
        )
    return user.organization_id


def _require_test_file_feature(db: Session, user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=user)
            if item.key == "release.accounting.ach_test_file"
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="$0 ACH Test File is not enabled.",
        )
    return user.organization_id


def _require_scope(current_user: User, owner_id: int) -> None:
    role = _role_value(current_user.role)
    if role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to manage owner ACH setup.",
        )
    if role == UserRole.OWNER.value and current_user.id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owners may only manage their own ACH setup.",
        )


@router.get("/{owner_id}/ach", response_model=OwnerACHOut)
def read_owner_ach(
    owner_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_feature(db, current_user)
    _require_scope(current_user, owner_id)
    try:
        return get_owner_ach(
            db,
            organization_id=organization_id,
            owner_id=owner_id,
        )
    except OwnerACHError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{owner_id}/ach", response_model=OwnerACHOut)
def save_owner_ach(
    owner_id: int,
    payload: OwnerACHUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_feature(db, current_user)
    _require_scope(current_user, owner_id)
    try:
        return upsert_owner_ach(
            db,
            organization_id=organization_id,
            owner_id=owner_id,
            payload=payload,
            actor=current_user,
        )
    except OwnerACHError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{owner_id}/ach/test-file/{bank_id}", response_model=ACHTestFileOut)
def create_owner_ach_test_file(
    owner_id: int,
    bank_id: int,
    payload: ACHTestFileIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_test_file_feature(db, current_user)
    _require_scope(current_user, owner_id)

    bank = (
        db.query(BankAccount)
        .options(joinedload(BankAccount.organization))
        .filter(
            BankAccount.id == bank_id,
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .first()
    )
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")

    owner_ach = (
        db.query(OwnerACHAccount)
        .filter(
            OwnerACHAccount.organization_id == organization_id,
            OwnerACHAccount.owner_id == owner_id,
            OwnerACHAccount.is_enabled.is_(True),
        )
        .first()
    )
    if owner_ach is None:
        raise HTTPException(
            status_code=400,
            detail="Owner ACH destination must be configured and enabled first.",
        )

    try:
        filename, content_type, content = generate_ach_test_file(
            bank=bank,
            organization=bank.organization,
            owner_ach=owner_ach,
            effective_date=payload.effective_date,
            company_id=payload.company_id,
            entry_description=payload.entry_description,
        )
    except ACHFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ACHTestFileOut(
        format=(bank.ach_format or "").upper(),
        filename=filename,
        content_type=content_type,
        content=content,
        owner_id=owner_id,
        amount=Decimal("0.00"),
    )
