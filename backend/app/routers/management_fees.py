# ============================================================
# management_fees.py (router)
# ------------------------------------------------------------
# Endpoints under /api/accounting/management-fees:
#
#   POST /preview             compute what would be charged
#   POST /run                 post the fee to the GL
#   GET  ""                   list past runs
#   GET  /{id}                one run detail
#   POST /{id}/reverse        reverse a run
#
# AppFolio parity — the fee is only computed from eligible
# receipt income; JEs never generate fees.
# ============================================================

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.management_fee_run import ManagementFeeRun
from app.schemas.management_fee import (
    FeePreviewIn,
    FeePreviewOut,
    FeeRunIn,
    FeeReverseIn,
    ManagementFeeRunListOut,
    ManagementFeeRunOut,
    EligibleIncomeLine,
)
from app.services.gl_posting import PostingError
from app.services.management_fee_posting import (
    preview_management_fee,
    run_management_fee,
    reverse_management_fee_run,
)


router = APIRouter(
    prefix="/api/accounting/management-fees",
    tags=["Management Fees"],
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


def _run_to_out(run: ManagementFeeRun) -> ManagementFeeRunOut:
    return ManagementFeeRunOut(
        id=run.id,
        organization_id=run.organization_id,
        property_id=run.property_id,
        property_name=run.property.name if run.property else None,
        period_start=run.period_start,
        period_end=run.period_end,
        rent_income_total=run.rent_income_total,
        other_fee_income_total=run.other_fee_income_total,
        rent_fee_pct=run.rent_fee_pct,
        other_fee_pct=run.other_fee_pct,
        rent_fee_amount=run.rent_fee_amount,
        other_fee_amount=run.other_fee_amount,
        total_fee=run.total_fee,
        expense_gl_account_id=run.expense_gl_account_id,
        expense_gl_account_number=(
            run.expense_gl_account.gl_number if run.expense_gl_account else None
        ),
        expense_gl_account_name=(
            run.expense_gl_account.name if run.expense_gl_account else None
        ),
        cash_gl_account_id=run.cash_gl_account_id,
        cash_gl_account_number=(
            run.cash_gl_account.gl_number if run.cash_gl_account else None
        ),
        cash_gl_account_name=(
            run.cash_gl_account.name if run.cash_gl_account else None
        ),
        gl_transaction_id=run.gl_transaction_id,
        notes=run.notes,
        is_reversed=run.is_reversed,
        reversal_of_id=run.reversal_of_id,
        is_active=run.is_active,
        created_by_id=run.created_by_id,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


# ============================================================
# POST /preview
# ============================================================

@router.post("/preview", response_model=FeePreviewOut)
def preview_fee(
    payload: FeePreviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    try:
        preview = preview_management_fee(
            db,
            organization_id=org_id,
            property_id=payload.property_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    except PostingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Convert line dicts into EligibleIncomeLine objects
    rent_lines = [EligibleIncomeLine(**l) for l in preview["rent_lines"]]
    other_lines = [EligibleIncomeLine(**l) for l in preview["other_lines"]]

    return FeePreviewOut(
        property_id=preview["property_id"],
        property_name=preview["property_name"],
        period_start=preview["period_start"],
        period_end=preview["period_end"],
        rent_income_total=preview["rent_income_total"],
        other_fee_income_total=preview["other_fee_income_total"],
        rent_fee_pct=preview["rent_fee_pct"],
        other_fee_pct=preview["other_fee_pct"],
        rent_fee_amount=preview["rent_fee_amount"],
        other_fee_amount=preview["other_fee_amount"],
        total_fee=preview["total_fee"],
        rent_lines=rent_lines,
        other_lines=other_lines,
        can_run=preview["can_run"],
        reason=preview["reason"],
    )


# ============================================================
# POST /run
# ============================================================

@router.post("/run", response_model=ManagementFeeRunOut, status_code=201)
def run_fee(
    payload: FeeRunIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    try:
        run = run_management_fee(
            db,
            organization_id=org_id,
            property_id=payload.property_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            expense_gl_account_id=payload.expense_gl_account_id,
            cash_gl_account_id=payload.cash_gl_account_id,
            notes=payload.notes,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run = (
        db.query(ManagementFeeRun)
        .options(
            joinedload(ManagementFeeRun.property),
            joinedload(ManagementFeeRun.expense_gl_account),
            joinedload(ManagementFeeRun.cash_gl_account),
        )
        .filter(ManagementFeeRun.id == run.id)
        .first()
    )
    return _run_to_out(run)


# ============================================================
# GET ""
# ============================================================

@router.get("", response_model=ManagementFeeRunListOut)
def list_runs(
    property_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    include_reversed: bool = Query(True),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    q = (
        db.query(ManagementFeeRun)
        .options(
            joinedload(ManagementFeeRun.property),
            joinedload(ManagementFeeRun.expense_gl_account),
            joinedload(ManagementFeeRun.cash_gl_account),
        )
        .filter(ManagementFeeRun.organization_id == org_id)
        .filter(ManagementFeeRun.is_active.is_(True))
    )
    if property_id is not None:
        q = q.filter(ManagementFeeRun.property_id == property_id)
    if date_from is not None:
        q = q.filter(ManagementFeeRun.period_end >= date_from)
    if date_to is not None:
        q = q.filter(ManagementFeeRun.period_start <= date_to)
    if not include_reversed:
        q = q.filter(ManagementFeeRun.is_reversed.is_(False))

    total = q.count()
    rows = (
        q.order_by(
            ManagementFeeRun.period_end.desc(),
            ManagementFeeRun.id.desc(),
        )
        .limit(limit)
        .all()
    )
    return ManagementFeeRunListOut(
        items=[_run_to_out(r) for r in rows],
        total=total,
    )


# ============================================================
# GET /{run_id}
# ============================================================

@router.get("/{run_id}", response_model=ManagementFeeRunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    run = (
        db.query(ManagementFeeRun)
        .options(
            joinedload(ManagementFeeRun.property),
            joinedload(ManagementFeeRun.expense_gl_account),
            joinedload(ManagementFeeRun.cash_gl_account),
        )
        .filter(
            ManagementFeeRun.id == run_id,
            ManagementFeeRun.organization_id == org_id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Fee run not found.")
    return _run_to_out(run)


# ============================================================
# POST /{run_id}/reverse
# ============================================================

@router.post(
    "/{run_id}/reverse",
    response_model=ManagementFeeRunOut,
    status_code=201,
)
def reverse_fee(
    run_id: int,
    payload: FeeReverseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    original = (
        db.query(ManagementFeeRun)
        .filter(
            ManagementFeeRun.id == run_id,
            ManagementFeeRun.organization_id == org_id,
        )
        .first()
    )
    if original is None:
        raise HTTPException(status_code=404, detail="Fee run not found.")

    try:
        mirror = reverse_management_fee_run(
            db=db,
            original=original,
            reversal_date=payload.reversal_date,
            memo=payload.memo,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run = (
        db.query(ManagementFeeRun)
        .options(
            joinedload(ManagementFeeRun.property),
            joinedload(ManagementFeeRun.expense_gl_account),
            joinedload(ManagementFeeRun.cash_gl_account),
        )
        .filter(ManagementFeeRun.id == mirror.id)
        .first()
    )
    return _run_to_out(run)