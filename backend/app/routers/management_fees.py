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
from app.models.user import Organization, User
from app.models.management_fee_run import ManagementFeeRun
from app.models.property import Property
from app.models.receipt import Receipt
from app.schemas.management_fee import (
    FeePreviewIn,
    FeePreviewOut,
    FeeRunIn,
    FeeReverseIn,
    ManagementFeeRunListOut,
    ManagementFeeRunOut,
    EligibleIncomeLine,
    OvercollectionStrategyOut,
    OvercollectionStrategyUpdate,
    ManagementFeeExclusionOut,
    ManagementFeeExclusionListOut,
)
from app.schemas.journal_entry import (
    GPRCandidateListOut,
    GPRCandidateOut,
    GPRPostIn,
    GPRPostResultOut,
)
from app.services.gl_posting import PostingError
from app.services.management_fee_posting import (
    preview_management_fee,
    run_management_fee,
    reverse_management_fee_run,
)
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user
from app.services.gpr_posting import list_gpr_candidates, month_bounds, post_gpr


router = APIRouter(
    prefix="/api/accounting/management-fees",
    tags=["Management Fees"],
)

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}
OVERCOLLECTION_FEATURE_KEY = "release.accounting.management_fees.overcollection"
MANAGEMENT_FEE_GPR_FEATURE_KEY = "release.accounting.management_fees.post_gpr"
EXCLUSIONS_FEATURE_KEY = "release.accounting.management_fees.exclusions"
DEFAULT_OVERCOLLECTION_STRATEGY = "CREDITS_THEN_RECEIPTS"


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


def _require_management_fees_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.MANAGEMENT_FEES"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Management Fees permission required.",
        )
    return org_id


def _require_write(current_user: User) -> None:
    if _norm_role(current_user.role) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to run or reverse management fees.",
        )


def _require_overcollection_feature(db: Session, current_user: User) -> int:
    org_id = _require_management_fees_access(db, current_user)
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == OVERCOLLECTION_FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Management fee overcollection strategy is not enabled.",
        )
    return org_id


def _require_management_fee_gpr_feature(db: Session, current_user: User) -> int:
    org_id = _require_management_fees_access(db, current_user)
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == MANAGEMENT_FEE_GPR_FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Management Fees Post GPR is not enabled.",
        )
    return org_id


def _require_exclusions_feature(db: Session, current_user: User) -> int:
    org_id = _require_management_fees_access(db, current_user)
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == EXCLUSIONS_FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Management Fee Exclusions is not enabled.",
        )
    return org_id


def _overcollection_out(org: Organization) -> OvercollectionStrategyOut:
    strategy = (
        org.management_fee_overcollection_strategy
        or DEFAULT_OVERCOLLECTION_STRATEGY
    )
    return OvercollectionStrategyOut(
        strategy=strategy,
        label=(
            "Credits then Receipts"
            if strategy == "CREDITS_THEN_RECEIPTS"
            else "Receipts then Credits"
        ),
        recommended=strategy == "CREDITS_THEN_RECEIPTS",
    )


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
    _require_write(current_user)
    org_id = _require_management_fees_access(db, current_user)
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
    _require_write(current_user)
    org_id = _require_management_fees_access(db, current_user)
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
    org_id = _require_management_fees_access(db, current_user)

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
# GET/PUT /overcollection-strategy
# ============================================================

@router.get(
    "/overcollection-strategy",
    response_model=OvercollectionStrategyOut,
)
def get_overcollection_strategy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_overcollection_feature(db, current_user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return _overcollection_out(org)


@router.put(
    "/overcollection-strategy",
    response_model=OvercollectionStrategyOut,
)
def update_overcollection_strategy(
    payload: OvercollectionStrategyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_overcollection_feature(db, current_user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")

    old_strategy = (
        org.management_fee_overcollection_strategy
        or DEFAULT_OVERCOLLECTION_STRATEGY
    )
    org.management_fee_overcollection_strategy = payload.strategy
    db.flush()
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=org_id,
        entity_type="organization",
        entity_id=org_id,
        action="management_fee_overcollection_strategy_updated",
        field_name="management_fee_overcollection_strategy",
        old_value=old_strategy,
        new_value=payload.strategy,
    )
    db.commit()
    db.refresh(org)
    return _overcollection_out(org)


# ============================================================
# GET/POST /post-gpr
# ============================================================

@router.get("/post-gpr", response_model=GPRCandidateListOut)
def get_management_fee_gpr_candidates(
    month: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_management_fee_gpr_feature(db, current_user)
    normalized, _ = month_bounds(month)
    try:
        rows = list_gpr_candidates(db, organization_id=org_id, month=normalized)
    except PostingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    items = [
        GPRCandidateOut(
            unit_id=row.unit_id,
            property_id=row.property_id,
            property_name=row.property_name,
            unit_number=row.unit_number,
            lease_id=row.lease_id,
            market_rent=row.market_rent,
            scheduled_rent=row.scheduled_rent,
            loss_gain=row.loss_gain,
            already_posted=row.already_posted,
            transaction_id=row.transaction_id,
        )
        for row in rows
    ]
    return GPRCandidateListOut(
        month=normalized,
        items=items,
        total=len(items),
        unposted=sum(1 for row in rows if not row.already_posted),
    )


@router.post("/post-gpr", response_model=GPRPostResultOut)
def post_management_fee_gpr(
    payload: GPRPostIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_management_fee_gpr_feature(db, current_user)
    normalized, _ = month_bounds(payload.month)
    try:
        transactions = post_gpr(
            db,
            organization_id=org_id,
            month=normalized,
            unit_ids=payload.unit_ids,
            created_by=current_user,
        )
    except PostingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return GPRPostResultOut(
        month=normalized,
        posted=len(transactions),
        transaction_ids=[row.id for row in transactions],
    )


# ============================================================
# GET /exclusions
# ============================================================

@router.get("/exclusions", response_model=ManagementFeeExclusionListOut)
def list_management_fee_exclusions(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    property_id: Optional[int] = Query(None),
    include_reversed: bool = Query(True),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_exclusions_feature(db, current_user)
    q = (
        db.query(Receipt, Property)
        .outerjoin(Property, Property.id == Receipt.property_id)
        .filter(
            Receipt.organization_id == org_id,
            Receipt.exclude_from_mgmt_fee.is_(True),
            Receipt.is_active.is_(True),
            Receipt.reversal_of_id.is_(None),
        )
    )
    if date_from is not None:
        q = q.filter(Receipt.receipt_date >= date_from)
    if date_to is not None:
        q = q.filter(Receipt.receipt_date <= date_to)
    if property_id is not None:
        q = q.filter(Receipt.property_id == property_id)
    if not include_reversed:
        q = q.filter(Receipt.is_reversed.is_(False))

    total = q.count()
    rows = (
        q.order_by(Receipt.receipt_date.desc(), Receipt.id.desc())
        .limit(limit)
        .all()
    )
    return ManagementFeeExclusionListOut(
        items=[
            ManagementFeeExclusionOut(
                receipt_id=receipt.id,
                receipt_date=receipt.receipt_date,
                receipt_type=receipt.type,
                amount=receipt.amount,
                property_id=receipt.property_id,
                property_name=prop.name if prop else None,
                reference_number=receipt.reference_number,
                source_name=(
                    receipt.received_from
                    or receipt.payer_name
                    or ("Tenant receipt" if receipt.tenant_user_id else None)
                ),
                remarks=receipt.remarks,
                is_reversed=receipt.is_reversed,
            )
            for receipt, prop in rows
        ],
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
    org_id = _require_management_fees_access(db, current_user)
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
    _require_write(current_user)
    org_id = _require_management_fees_access(db, current_user)
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