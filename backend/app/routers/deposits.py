# ============================================================
# deposits.py (router)
# ------------------------------------------------------------
# HTTP endpoints for Bank Deposits (Phase 2 Step 7).
#
#   GET    /api/accounting/deposits                    list
#   GET    /api/accounting/deposits/undeposited-receipts
#                                                      picker
#   GET    /api/accounting/deposits/{id}               detail
#   POST   /api/accounting/deposits                    create
#
# Deposits do NOT post to the GL — receipts already credited
# cash when they were posted. Deposits just tag receipts as
# deposited (via deposit_lines).
# ============================================================

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.receipt import Receipt
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.schemas.deposit import (
    DepositCreateIn,
    DepositDetailOut,
    DepositLineOut,
    DepositListOut,
    DepositOut,
    UndepositedReceiptRow,
    UndepositedReceiptsOut,
)
from app.services.gl_posting import PostingError
from app.services.menu_resolver import permission_allows_user
from app.services.deposit_posting import (
    create_deposit,
    list_undeposited_receipts,
)


router = APIRouter(
    prefix="/api/accounting/deposits",
    tags=["Deposits"],
)


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


def _require_deposits_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.DEPOSITS"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deposits permission required.",
        )
    return org_id


def _receipt_payer_label(r: Receipt) -> str:
    if r.type == "TENANT" and r.tenant_user_id is not None:
        return f"Tenant #{r.tenant_user_id}"
    if r.type == "OWNER":
        return r.payer_name or (
            f"Owner #{r.owner_user_id}"
            if r.owner_user_id is not None
            else "Owner"
        )
    if r.type == "OTHER":
        return r.received_from or "Other"
    return r.type


def _deposit_to_out(d: Deposit) -> DepositOut:
    return DepositOut(
        id=d.id,
        organization_id=d.organization_id,
        bank_gl_account_id=d.bank_gl_account_id,
        bank_gl_account_number=(
            d.bank_gl_account.gl_number if d.bank_gl_account else None
        ),
        bank_gl_account_name=(
            d.bank_gl_account.name if d.bank_gl_account else None
        ),
        deposit_date=d.deposit_date,
        deposit_number=d.deposit_number,
        description=d.description,
        total=d.total,
        notes=d.notes,
        is_active=d.is_active,
        created_by_id=d.created_by_id,
        created_at=d.created_at,
        updated_at=d.updated_at,
        line_count=len(d.lines) if d.lines is not None else 0,
    )


def _detail_out(d: Deposit) -> DepositDetailOut:
    base = _deposit_to_out(d)

    lines_out = []
    for ln in d.lines:
        r = ln.receipt
        lines_out.append(
            DepositLineOut(
                id=ln.id,
                deposit_id=ln.deposit_id,
                receipt_id=ln.receipt_id,
                receipt_date=r.receipt_date if r else None,
                receipt_type=r.type if r else None,
                receipt_amount=r.amount if r else None,
                receipt_reference=(
                    r.reference_number if r else None
                ),
                receipt_payer=(
                    _receipt_payer_label(r) if r else None
                ),
            )
        )

    return DepositDetailOut(**base.model_dump(), lines=lines_out)


# ============================================================
# GET /api/accounting/deposits  -- list
# ============================================================

@router.get("", response_model=DepositListOut)
def list_deposits(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    bank_gl_account_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_deposits_access(db, current_user)

    q = (
        db.query(Deposit)
        .options(
            joinedload(Deposit.bank_gl_account),
            joinedload(Deposit.lines),
        )
        .filter(Deposit.organization_id == org_id)
        .filter(Deposit.is_active.is_(True))
    )

    if date_from is not None:
        q = q.filter(Deposit.deposit_date >= date_from)
    if date_to is not None:
        q = q.filter(Deposit.deposit_date <= date_to)
    if bank_gl_account_id is not None:
        q = q.filter(Deposit.bank_gl_account_id == bank_gl_account_id)

    total = q.count()
    rows = (
        q.order_by(Deposit.deposit_date.desc(), Deposit.id.desc())
        .limit(limit)
        .all()
    )

    return DepositListOut(
        items=[_deposit_to_out(d) for d in rows],
        total=total,
    )


# ============================================================
# GET /api/accounting/deposits/undeposited-receipts
# ------------------------------------------------------------
# Returns receipts that are not yet in any deposit. Optional
# filter by bank_gl_account_id.
#
# NOTE: this route MUST be defined before /{deposit_id} or
# FastAPI will try to parse "undeposited-receipts" as an int.
# ============================================================

@router.get(
    "/undeposited-receipts", response_model=UndepositedReceiptsOut
)
def get_undeposited_receipts(
    bank_gl_account_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_deposits_access(db, current_user)

    receipts = list_undeposited_receipts(
        db,
        organization_id=org_id,
        bank_gl_account_id=bank_gl_account_id,
    )

    items = []
    total_amount = Decimal("0")
    for r in receipts:
        total_amount += Decimal(r.amount or 0)
        items.append(
            UndepositedReceiptRow(
                id=r.id,
                receipt_date=r.receipt_date,
                type=r.type,
                amount=r.amount,
                reference_number=r.reference_number,
                cash_gl_account_id=r.cash_gl_account_id,
                cash_gl_account_number=(
                    r.cash_gl_account.gl_number
                    if r.cash_gl_account
                    else None
                ),
                cash_gl_account_name=(
                    r.cash_gl_account.name
                    if r.cash_gl_account
                    else None
                ),
                payer_label=_receipt_payer_label(r),
            )
        )

    return UndepositedReceiptsOut(
        items=items,
        total=len(items),
        total_amount=total_amount,
    )


# ============================================================
# GET /api/accounting/deposits/{deposit_id}  -- detail
# ============================================================

@router.get("/{deposit_id}", response_model=DepositDetailOut)
def get_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_deposits_access(db, current_user)

    d = (
        db.query(Deposit)
        .options(
            joinedload(Deposit.bank_gl_account),
            joinedload(Deposit.lines).joinedload(DepositLine.receipt),
        )
        .filter(
            Deposit.id == deposit_id,
            Deposit.organization_id == org_id,
        )
        .first()
    )
    if d is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found.",
        )

    return _detail_out(d)


# ============================================================
# POST /api/accounting/deposits  -- create
# ============================================================

@router.post(
    "",
    response_model=DepositDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_deposit_endpoint(
    payload: DepositCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_deposits_access(db, current_user)

    try:
        deposit = create_deposit(
            db=db,
            organization_id=org_id,
            bank_gl_account_id=payload.bank_gl_account_id,
            deposit_date=payload.deposit_date,
            deposit_number=payload.deposit_number,
            description=payload.description,
            notes=payload.notes,
            receipt_ids=payload.receipt_ids,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    d = (
        db.query(Deposit)
        .options(
            joinedload(Deposit.bank_gl_account),
            joinedload(Deposit.lines).joinedload(DepositLine.receipt),
        )
        .filter(Deposit.id == deposit.id)
        .first()
    )

    return _detail_out(d)