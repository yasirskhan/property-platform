# ============================================================
# bills.py (router)
# ------------------------------------------------------------
# HTTP endpoints for Bills (Phase 2 Step 6).
#
#   GET    /api/accounting/bills                    list
#   GET    /api/accounting/bills/{id}               detail
#   POST   /api/accounting/bills                    enter bill
#   POST   /api/accounting/bills/{id}/pay           pay bill
#   POST   /api/accounting/bills/{id}/reverse       reverse (unpaid)
#
# Two-step accrual:
#   Enter  -> DR Expense / CR AP
#   Pay    -> DR AP     / CR Cash
#
# All routes are org-scoped.
# ============================================================

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.schemas.bill import (
    BillCreateIn,
    BillDetailOut,
    BillLineOut,
    BillListOut,
    BillOut,
    BillPayIn,
    BillReverseIn,
)
from app.services.gl_posting import PostingError
from app.services.bill_posting import (
    post_bill,
    pay_bill,
    reverse_bill,
)


router = APIRouter(
    prefix="/api/accounting/bills",
    tags=["Bills"],
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


def _bill_to_out(b: Bill) -> BillOut:
    return BillOut(
        id=b.id,
        organization_id=b.organization_id,
        bill_number=b.bill_number,
        payee_name=b.payee_name,
        payee_user_id=b.payee_user_id,
        bill_date=b.bill_date,
        due_date=b.due_date,
        reference_number=b.reference_number,
        amount=b.amount,
        amount_paid=b.amount_paid,
        status=b.status,
        property_id=b.property_id,
        unit_id=b.unit_id,
        payable_gl_account_id=b.payable_gl_account_id,
        payable_gl_account_number=(
            b.payable_gl_account.gl_number if b.payable_gl_account else None
        ),
        payable_gl_account_name=(
            b.payable_gl_account.name if b.payable_gl_account else None
        ),
        remarks=b.remarks,
        notes=b.notes,
        source_type=b.source_type,
        source_id=b.source_id,
        gl_transaction_id=b.gl_transaction_id,
        is_reversed=b.is_reversed,
        reversal_of_id=b.reversal_of_id,
        is_active=b.is_active,
        created_by_id=b.created_by_id,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


def _detail_out(b: Bill) -> BillDetailOut:
    base = _bill_to_out(b)
    lines_out = [
        BillLineOut(
            id=ln.id,
            bill_id=ln.bill_id,
            gl_account_id=ln.gl_account_id,
            gl_account_number=(
                ln.gl_account.gl_number if ln.gl_account else None
            ),
            gl_account_name=(
                ln.gl_account.name if ln.gl_account else None
            ),
            property_id=ln.property_id,
            unit_id=ln.unit_id,
            description=ln.description,
            amount=ln.amount,
        )
        for ln in b.lines
    ]
    return BillDetailOut(**base.model_dump(), lines=lines_out)


# ============================================================
# GET /api/accounting/bills  -- list, filterable
# ============================================================

@router.get("", response_model=BillListOut)
def list_bills(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    property_id: Optional[int] = Query(None),
    payee_name: Optional[str] = Query(None),
    include_reversed: bool = Query(True),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    q = (
        db.query(Bill)
        .options(joinedload(Bill.payable_gl_account))
        .filter(Bill.organization_id == org_id)
        .filter(Bill.is_active.is_(True))
    )

    if date_from is not None:
        q = q.filter(Bill.bill_date >= date_from)
    if date_to is not None:
        q = q.filter(Bill.bill_date <= date_to)
    if status_filter is not None:
        q = q.filter(Bill.status == status_filter.strip().upper())
    if property_id is not None:
        q = q.filter(Bill.property_id == property_id)
    if payee_name:
        q = q.filter(Bill.payee_name.ilike(f"%{payee_name}%"))
    if not include_reversed:
        q = q.filter(Bill.is_reversed.is_(False))

    total = q.count()
    rows = (
        q.order_by(Bill.bill_date.desc(), Bill.id.desc())
        .limit(limit)
        .all()
    )

    return BillListOut(
        items=[_bill_to_out(b) for b in rows],
        total=total,
    )


# ============================================================
# GET /api/accounting/bills/{bill_id}  -- detail + lines
# ============================================================

@router.get("/{bill_id}", response_model=BillDetailOut)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    b = (
        db.query(Bill)
        .options(
            joinedload(Bill.payable_gl_account),
            joinedload(Bill.lines).joinedload(BillLine.gl_account),
        )
        .filter(
            Bill.id == bill_id,
            Bill.organization_id == org_id,
        )
        .first()
    )
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found.",
        )

    return _detail_out(b)


# ============================================================
# POST /api/accounting/bills  -- enter bill
# ============================================================

@router.post(
    "",
    response_model=BillDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_bill(
    payload: BillCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    try:
        bill = post_bill(
            db=db,
            organization_id=org_id,
            payload=payload,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    b = (
        db.query(Bill)
        .options(
            joinedload(Bill.payable_gl_account),
            joinedload(Bill.lines).joinedload(BillLine.gl_account),
        )
        .filter(Bill.id == bill.id)
        .first()
    )

    return _detail_out(b)


# ============================================================
# POST /api/accounting/bills/{id}/pay
# ============================================================

@router.post(
    "/{bill_id}/pay",
    response_model=BillDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def pay_bill_endpoint(
    bill_id: int,
    payload: BillPayIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    bill = (
        db.query(Bill)
        .filter(
            Bill.id == bill_id,
            Bill.organization_id == org_id,
        )
        .first()
    )
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found.",
        )

    try:
        pay_bill(
            db=db,
            organization_id=org_id,
            bill=bill,
            payload=payload,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    b = (
        db.query(Bill)
        .options(
            joinedload(Bill.payable_gl_account),
            joinedload(Bill.lines).joinedload(BillLine.gl_account),
        )
        .filter(Bill.id == bill.id)
        .first()
    )

    return _detail_out(b)


# ============================================================
# POST /api/accounting/bills/{id}/reverse
# ============================================================

@router.post(
    "/{bill_id}/reverse",
    response_model=BillDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def reverse_bill_endpoint(
    bill_id: int,
    payload: BillReverseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    original = (
        db.query(Bill)
        .filter(
            Bill.id == bill_id,
            Bill.organization_id == org_id,
        )
        .first()
    )
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found.",
        )

    try:
        mirror = reverse_bill(
            db=db,
            original=original,
            reversal_date=payload.reversal_date,
            memo=payload.memo,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    b = (
        db.query(Bill)
        .options(
            joinedload(Bill.payable_gl_account),
            joinedload(Bill.lines).joinedload(BillLine.gl_account),
        )
        .filter(Bill.id == mirror.id)
        .first()
    )

    return _detail_out(b)