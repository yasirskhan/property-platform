# ============================================================
# bank_accounts.py (router)
# ------------------------------------------------------------
#   GET    /api/accounting/bank-accounts         list
#   GET    /api/accounting/bank-accounts/{id}    detail
#   POST   /api/accounting/bank-accounts         create
#   PATCH  /api/accounting/bank-accounts/{id}    update
#   DELETE /api/accounting/bank-accounts/{id}    soft delete
#
# No GL posting here — bank accounts map to existing GL
# cash accounts (1150, 1160). They're configuration, not
# transactions.
# ============================================================

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.services.menu_resolver import permission_allows_user
from app.schemas.bank_account import (
    BankAccountCreateIn,
    BankAccountListOut,
    BankAccountOut,
    BankAccountUpdateIn,
)


router = APIRouter(
    prefix="/api/accounting/bank-accounts",
    tags=["Bank Accounts"],
)

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _norm_role(role) -> str:
    if role is None:
        return ""
    value = role.value if hasattr(role, "value") else str(role)
    return value.upper()


def _require_bank_accounts_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.BANK_ACCOUNTS"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bank Accounts permission required.",
        )
    return org_id


def _require_write(current_user: User) -> None:
    if _norm_role(current_user.role) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to modify bank accounts.",
        )


def _to_out(b: BankAccount) -> BankAccountOut:
    return BankAccountOut(
        id=b.id,
        organization_id=b.organization_id,
        name=b.name,
        bank_name=b.bank_name,
        routing_number=b.routing_number,
        account_number=b.account_number,
        gl_account_id=b.gl_account_id,
        gl_account_number=(
            b.gl_account.gl_number if b.gl_account else None
        ),
        gl_account_name=(
            b.gl_account.name if b.gl_account else None
        ),
        account_type=b.account_type,
        ach_format=b.ach_format,
        notes=b.notes,
        is_active=b.is_active,
        created_by_id=b.created_by_id,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


# ============================================================
# GET ""
# ============================================================

@router.get("", response_model=BankAccountListOut)
def list_bank_accounts(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_bank_accounts_access(db, current_user)

    q = (
        db.query(BankAccount)
        .options(joinedload(BankAccount.gl_account))
        .filter(BankAccount.organization_id == org_id)
    )
    if not include_inactive:
        q = q.filter(BankAccount.is_active.is_(True))

    total = q.count()
    rows = (
        q.order_by(
            BankAccount.account_type.asc(),
            BankAccount.name.asc(),
        )
        .all()
    )

    return BankAccountListOut(
        items=[_to_out(b) for b in rows],
        total=total,
    )


# ============================================================
# GET /{id}
# ============================================================

@router.get("/{bank_account_id}", response_model=BankAccountOut)
def get_bank_account(
    bank_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_bank_accounts_access(db, current_user)

    b = (
        db.query(BankAccount)
        .options(joinedload(BankAccount.gl_account))
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.organization_id == org_id,
        )
        .first()
    )
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found.",
        )
    return _to_out(b)


# ============================================================
# POST ""
# ============================================================

@router.post(
    "",
    response_model=BankAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def create_bank_account(
    payload: BankAccountCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_bank_accounts_access(db, current_user)

    # Verify the GL account belongs to us
    gl = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == payload.gl_account_id,
            GLAccount.organization_id == org_id,
        )
        .first()
    )
    if gl is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GL account not found in your organization.",
        )
    if not gl.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GL account is inactive.",
        )

    # Enforce unique (org, gl) at the app layer too (nice error message)
    existing = (
        db.query(BankAccount)
        .filter(
            BankAccount.organization_id == org_id,
            BankAccount.gl_account_id == payload.gl_account_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"GL account {gl.gl_number} already has a bank account "
                f"({existing.name})."
            ),
        )

    try:
        b = BankAccount(
            organization_id=org_id,
            name=payload.name,
            bank_name=payload.bank_name,
            routing_number=payload.routing_number,
            account_number=payload.account_number,
            gl_account_id=payload.gl_account_id,
            account_type=payload.account_type,
            ach_format=payload.ach_format,
            notes=payload.notes,
            is_active=True,
            created_by_id=current_user.id if current_user else None,
        )
        db.add(b)
        db.commit()
        db.refresh(b)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create bank account: {e}",
        )

    # Reload with GL account
    b = (
        db.query(BankAccount)
        .options(joinedload(BankAccount.gl_account))
        .filter(BankAccount.id == b.id)
        .first()
    )
    return _to_out(b)


# ============================================================
# PATCH /{id}
# ============================================================

@router.patch("/{bank_account_id}", response_model=BankAccountOut)
def update_bank_account(
    bank_account_id: int,
    payload: BankAccountUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_bank_accounts_access(db, current_user)

    b = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.organization_id == org_id,
        )
        .first()
    )
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(b, key, value)

    try:
        db.commit()
        db.refresh(b)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update bank account: {e}",
        )

    b = (
        db.query(BankAccount)
        .options(joinedload(BankAccount.gl_account))
        .filter(BankAccount.id == b.id)
        .first()
    )
    return _to_out(b)


# ============================================================
# DELETE /{id} — soft delete
# ============================================================

@router.delete("/{bank_account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_account(
    bank_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_bank_accounts_access(db, current_user)

    b = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.organization_id == org_id,
        )
        .first()
    )
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found.",
        )

    b.is_active = False
    db.commit()
    return None