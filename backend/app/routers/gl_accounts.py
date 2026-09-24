# ============================================================
# gl_accounts.py (router)
# ------------------------------------------------------------
# Endpoints:
#   GET    /api/accounting/gl-accounts              list (grouped)
#   GET    /api/accounting/gl-accounts/{id}         get one
#   POST   /api/accounting/gl-accounts              create (custom account)
#   PUT    /api/accounting/gl-accounts/{id}         update
#   DELETE /api/accounting/gl-accounts/{id}         soft delete
#
# Permission rule (temporary until the GL Account Permissions
# feature ships):
#   Read: any logged-in user in the org
#   Write: ADMIN, OWNER, MANAGER only
#
# All operations are scoped to the caller's own organization.
# A user can never read or write another org's accounts.
# ============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.audit import log_action
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.gl_account import GLAccount, ACCOUNT_TYPES
from app.services.menu_resolver import permission_allows_user
from app.schemas.gl_account import (
    GLAccountCreate,
    GLAccountUpdate,
    GLAccountOut,
    GLAccountListOut,
    GLAccountGroup,
)

router = APIRouter(prefix="/api/accounting/gl-accounts", tags=["GL Accounts"])

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _norm_role(role) -> str:
    if role is None:
        return ""
    value = role.value if hasattr(role, "value") else str(role)
    return value.upper()


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _require_gl_accounts_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.GL_ACCOUNTS"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GL Accounts permission required.",
        )
    return org_id


def _require_write(current_user: User) -> None:
    if _norm_role(current_user.role) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to modify GL accounts.",
        )


def _fetch_or_404(db: Session, org_id: int, account_id: int) -> GLAccount:
    acct = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == account_id,
            GLAccount.organization_id == org_id,
        )
        .first()
    )
    if acct is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GL account not found.",
        )
    return acct


# ============================================================
# GET /api/accounting/gl-accounts  — list, grouped by type
# ============================================================

@router.get("", response_model=GLAccountListOut)
def list_gl_accounts(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_gl_accounts_access(db, current_user)

    q = db.query(GLAccount).filter(GLAccount.organization_id == org_id)
    if not include_inactive:
        q = q.filter(GLAccount.is_active.is_(True))

    accounts = q.order_by(GLAccount.gl_number).all()

    by_type: dict[str, list[GLAccount]] = {
        "ASSET": [], "LIABILITY": [], "EQUITY": [], "INCOME": [], "EXPENSE": []
    }
    for a in accounts:
        by_type.setdefault(a.account_type, []).append(a)

    groups: List[GLAccountGroup] = []
    for t in ("ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"):
        if by_type.get(t):
            groups.append(
                GLAccountGroup(
                    account_type=t,
                    accounts=[GLAccountOut.model_validate(a) for a in by_type[t]],
                )
            )

    return GLAccountListOut(groups=groups, total=len(accounts))


# ============================================================
# GET /api/accounting/gl-accounts/{account_id}
# ============================================================

@router.get("/{account_id}", response_model=GLAccountOut)
def get_gl_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_gl_accounts_access(db, current_user)
    return _fetch_or_404(db, org_id, account_id)


# ============================================================
# POST /api/accounting/gl-accounts  — create a custom account
# ============================================================

@router.post("", response_model=GLAccountOut, status_code=status.HTTP_201_CREATED)
def create_gl_account(
    payload: GLAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_gl_accounts_access(db, current_user)

    account_type = payload.account_type.upper()
    if account_type not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account_type must be one of {', '.join(ACCOUNT_TYPES)}",
        )

    # Unique gl_number per org
    existing = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == org_id,
            GLAccount.gl_number == payload.gl_number,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GL number {payload.gl_number} already exists in your organization.",
        )

    # Validate sub_account_of points to an account in the same org
    if payload.sub_account_of is not None:
        _fetch_or_404(db, org_id, payload.sub_account_of)

    account = GLAccount(
        organization_id=org_id,
        gl_number=payload.gl_number,
        name=payload.name,
        account_type=account_type,
        sub_account_of=payload.sub_account_of,
        offset_account=payload.offset_account,
        subject_to_mgmt_fees=payload.subject_to_mgmt_fees,
        include_on_cash_flow=payload.include_on_cash_flow,
        must_clear=payload.must_clear,
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    log_action(
        db=db,
        user=current_user,
        entity_type="gl_account",
        entity_id=account.id,
        action="create",
        field_name=None,
        old_value=None,
        new_value=f"{account.gl_number} {account.name}",
    )

    return account


# ============================================================
# PUT /api/accounting/gl-accounts/{account_id}  — update
# ============================================================

@router.put("/{account_id}", response_model=GLAccountOut)
def update_gl_account(
    account_id: int,
    payload: GLAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_gl_accounts_access(db, current_user)
    account = _fetch_or_404(db, org_id, account_id)

    data = payload.model_dump(exclude_unset=True)

    if "account_type" in data and data["account_type"] is not None:
        new_type = data["account_type"].upper()
        if new_type not in ACCOUNT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"account_type must be one of {', '.join(ACCOUNT_TYPES)}",
            )
        data["account_type"] = new_type

    if "sub_account_of" in data and data["sub_account_of"] is not None:
        if data["sub_account_of"] == account.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account cannot be its own parent.",
            )
        _fetch_or_404(db, org_id, data["sub_account_of"])

    # Track changes for the audit log
    changes = []
    for field, new_value in data.items():
        old_value = getattr(account, field)
        if old_value != new_value:
            changes.append((field, old_value, new_value))
            setattr(account, field, new_value)

    if not changes:
        return account

    db.commit()
    db.refresh(account)

    for field, old_value, new_value in changes:
        log_action(
            db=db,
            user=current_user,
            entity_type="gl_account",
            entity_id=account.id,
            action="update",
            field_name=field,
            old_value=str(old_value),
            new_value=str(new_value),
        )

    return account


# ============================================================
# DELETE /api/accounting/gl-accounts/{account_id}  — soft delete
# ============================================================

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gl_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_org(current_user)
    account = _fetch_or_404(db, org_id, account_id)

    if not account.is_active:
        return None

    account.is_active = False
    from datetime import datetime
    account.deleted_at = datetime.utcnow()
    account.deleted_by_id = current_user.id

    db.commit()

    log_action(
        db=db,
        user=current_user,
        entity_type="gl_account",
        entity_id=account.id,
        action="deactivate",
        field_name="is_active",
        old_value="True",
        new_value="False",
    )

    return None