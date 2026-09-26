# ============================================================
# receipts.py (router)
# ------------------------------------------------------------
# HTTP endpoints for Receipts (Phase 2 Step 5).
#
#   GET    /api/accounting/receipts                        list
#   GET    /api/accounting/receipts/{id}                   detail
#   POST   /api/accounting/receipts                        create+post
#   POST   /api/accounting/receipts/{id}/reverse           reverse
#   GET    /api/accounting/receipts/tenant/{user_id}/open-charges
#                                                          charges table
#
# All routes are org-scoped. The current user's organization
# is the only one they can see or touch.
#
# As of Step 8a, owner_id is passed through from the ORM to
# the response so the trust sub-ledger and reconciliation
# have the tag available on every receipt.
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
from app.models.receipt_line import ReceiptLine
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.schemas.receipt import (
    ReceiptCreateIn,
    ReceiptDetailOut,
    ReceiptLineOut,
    ReceiptListOut,
    ReceiptOut,
    ReceiptReverseIn,
    ReceiptNSFIn,
)
from app.services.gl_posting import PostingError
from app.services.receipt_posting import post_receipt, reverse_receipt, process_nsf_receipt
from app.services.menu_resolver import permission_allows_user
from app.services.customer_features import resolve_customer_features


router = APIRouter(
    prefix="/api/accounting/receipts",
    tags=["Receipts"],
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


def _require_receipts_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.RECEIVABLES"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receivables permission required.")
    return org_id


def _require_receipt_feature(
    db: Session,
    current_user: User,
    feature_key: str,
) -> None:
    decisions = {
        row.key: row
        for row in resolve_customer_features(db, user=current_user)
    }
    decision = decisions.get(feature_key)
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt capability is not available.",
        )


def _deposit_ids(
    db: Session,
    *,
    organization_id: int,
    receipt_ids: list[int],
) -> dict[int, int]:
    if not receipt_ids:
        return {}
    return {
        receipt_id: deposit_id
        for receipt_id, deposit_id in (
            db.query(DepositLine.receipt_id, DepositLine.deposit_id)
            .filter(
                DepositLine.organization_id == organization_id,
                DepositLine.receipt_id.in_(receipt_ids),
            )
            .all()
        )
    }


def _receipt_to_out(r: Receipt, deposit_id: int | None = None) -> ReceiptOut:
    return ReceiptOut(
        id=r.id,
        organization_id=r.organization_id,
        type=r.type,
        receipt_date=r.receipt_date,
        amount=r.amount,
        cash_gl_account_id=r.cash_gl_account_id,
        cash_gl_account_number=(
            r.cash_gl_account.gl_number if r.cash_gl_account else None
        ),
        cash_gl_account_name=(
            r.cash_gl_account.name if r.cash_gl_account else None
        ),
        tenant_user_id=r.tenant_user_id,
        owner_user_id=r.owner_user_id,
        income_gl_account_id=r.income_gl_account_id,
        payer_name=r.payer_name,
        received_from=r.received_from,
        exclude_from_mgmt_fee=r.exclude_from_mgmt_fee,
        property_id=r.property_id,
        unit_id=r.unit_id,
        owner_id=r.owner_id,
        reference_number=r.reference_number,
        remarks=r.remarks,
        notes=r.notes,
        gl_transaction_id=r.gl_transaction_id,
        deposit_id=deposit_id,
        is_deposited=deposit_id is not None,
        is_reversed=r.is_reversed,
        reversal_of_id=r.reversal_of_id,
        is_active=r.is_active,
        created_by_id=r.created_by_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _detail_out(r: Receipt, deposit_id: int | None = None) -> ReceiptDetailOut:
    base = _receipt_to_out(r, deposit_id)
    lines_out = [
        ReceiptLineOut(
            id=ln.id,
            receipt_id=ln.receipt_id,
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
            amount_to_pay=ln.amount_to_pay,
            line_date=ln.line_date,
            is_prepayment=ln.is_prepayment,
        )
        for ln in r.lines
    ]
    return ReceiptDetailOut(**base.model_dump(), lines=lines_out)


# ============================================================
# GET /api/accounting/receipts  -- list, filterable
# ============================================================

@router.get("", response_model=ReceiptListOut)
def list_receipts(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    type: Optional[str] = Query(None),
    property_id: Optional[int] = Query(None),
    include_reversed: bool = Query(True),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)

    q = (
        db.query(Receipt)
        .options(joinedload(Receipt.cash_gl_account))
        .filter(Receipt.organization_id == org_id)
        .filter(Receipt.is_active.is_(True))
    )

    if date_from is not None:
        q = q.filter(Receipt.receipt_date >= date_from)
    if date_to is not None:
        q = q.filter(Receipt.receipt_date <= date_to)
    if type is not None:
        q = q.filter(Receipt.type == type.strip().upper())
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

    deposit_map = _deposit_ids(
        db,
        organization_id=org_id,
        receipt_ids=[row.id for row in rows],
    )
    return ReceiptListOut(
        items=[_receipt_to_out(row, deposit_map.get(row.id)) for row in rows],
        total=total,
    )


# ============================================================
# GET /api/accounting/receipts/tenant/{user_id}/open-charges
# ------------------------------------------------------------
# Returns unpaid/partial rent invoices for the tenant's active
# lease. Used to auto-fill the charges table on the New Tenant
# Receipt screen.
#
# NOTE: Lease has no organization_id. We scope through the
# property that owns the lease's unit. Also, Lease uses
# tenant_id (not tenant_user_id).
# ============================================================

@router.get("/tenant/{user_id}/open-charges")
def list_tenant_open_charges(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)

    # The tenant must belong to this org
    tenant = (
        db.query(User)
        .filter(User.id == user_id, User.organization_id == org_id)
        .first()
    )
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found.",
        )

    from app.models.lease import Lease, RentInvoice
    from app.models.property import Property, Unit

    # Find the tenant's active lease (or most recent lease).
    # Lease is scoped to org via Unit -> Property.
    lease = (
        db.query(Lease)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == org_id,
            Lease.tenant_id == user_id,
        )
        .order_by(Lease.id.desc())
        .first()
    )

    # Default rent GL account (4100 Rent), fall back to any INCOME account.
    rent_account = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == org_id,
            GLAccount.gl_number == "4100",
        )
        .first()
    )
    fallback_account = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == org_id,
            GLAccount.account_type == "INCOME",
            GLAccount.is_active.is_(True),
        )
        .order_by(GLAccount.gl_number)
        .first()
    )
    rent_gl_id = (
        rent_account.id
        if rent_account
        else (fallback_account.id if fallback_account else None)
    )
    rent_gl_number = (
        rent_account.gl_number
        if rent_account
        else (fallback_account.gl_number if fallback_account else None)
    )
    rent_gl_name = (
        rent_account.name
        if rent_account
        else (fallback_account.name if fallback_account else None)
    )

    if lease is None:
        return {
            "items": [],
            "total": 0,
            "lease_id": None,
            "rent_gl_account_id": rent_gl_id,
            "rent_gl_account_number": rent_gl_number,
            "rent_gl_account_name": rent_gl_name,
        }

    invoices = (
        db.query(RentInvoice)
        .filter(RentInvoice.lease_id == lease.id)
        .all()
    )

    items = []
    for inv in invoices:
        due = Decimal(inv.amount_due or 0)
        paid = Decimal(inv.amount_paid or 0)
        balance = due - paid
        if balance <= 0:
            continue
        period = ""
        if inv.period_start and inv.period_end:
            period = f" ({inv.period_start} to {inv.period_end})"
        items.append(
            {
                "charge_id": inv.id,
                "charge_date": inv.due_date.isoformat() if inv.due_date else None,
                "description": f"Rent{period}",
                "balance": str(balance),
                "amount_due": str(due),
                "amount_paid": str(paid),
                "gl_account_id": rent_gl_id,
                "gl_account_number": rent_gl_number,
                "gl_account_name": rent_gl_name,
            }
        )

    items.sort(key=lambda x: x.get("charge_date") or "")

    return {
        "items": items,
        "total": len(items),
        "lease_id": lease.id,
        "rent_gl_account_id": rent_gl_id,
        "rent_gl_account_number": rent_gl_number,
        "rent_gl_account_name": rent_gl_name,
    }


# ============================================================
# GET /api/accounting/receipts/{receipt_id}  -- detail + lines
# ============================================================

@router.get("/{receipt_id}", response_model=ReceiptDetailOut)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)

    r = (
        db.query(Receipt)
        .options(
            joinedload(Receipt.cash_gl_account),
            joinedload(Receipt.lines).joinedload(ReceiptLine.gl_account),
        )
        .filter(
            Receipt.id == receipt_id,
            Receipt.organization_id == org_id,
        )
        .first()
    )
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found.",
        )

    deposit_map = _deposit_ids(
        db, organization_id=org_id, receipt_ids=[r.id]
    )
    return _detail_out(r, deposit_map.get(r.id))


# ============================================================
# RECEIPT ACTION DATA / PROCESSING
# ============================================================

@router.get("/{receipt_id}/print-data", response_model=ReceiptDetailOut)
def get_receipt_print_data(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)
    _require_receipt_feature(
        db, current_user, "release.accounting.receipts.print"
    )
    r = (
        db.query(Receipt)
        .options(
            joinedload(Receipt.cash_gl_account),
            joinedload(Receipt.lines).joinedload(ReceiptLine.gl_account),
        )
        .filter(
            Receipt.id == receipt_id,
            Receipt.organization_id == org_id,
        )
        .first()
    )
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found.",
        )
    deposit_map = _deposit_ids(
        db, organization_id=org_id, receipt_ids=[r.id]
    )
    return _detail_out(r, deposit_map.get(r.id))


@router.get("/{receipt_id}/repeat-data", response_model=ReceiptDetailOut)
def get_receipt_repeat_data(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)
    _require_receipt_feature(
        db, current_user, "release.accounting.receipts.repeat"
    )
    r = (
        db.query(Receipt)
        .options(
            joinedload(Receipt.cash_gl_account),
            joinedload(Receipt.lines).joinedload(ReceiptLine.gl_account),
        )
        .filter(
            Receipt.id == receipt_id,
            Receipt.organization_id == org_id,
        )
        .first()
    )
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found.",
        )
    deposit_map = _deposit_ids(
        db, organization_id=org_id, receipt_ids=[r.id]
    )
    return _detail_out(r, deposit_map.get(r.id))


@router.post("/{receipt_id}/process-nsf", response_model=ReceiptDetailOut)
def process_receipt_nsf_endpoint(
    receipt_id: int,
    payload: ReceiptNSFIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)
    _require_receipt_feature(
        db, current_user, "release.accounting.receipts.process_nsf"
    )
    original = (
        db.query(Receipt)
        .filter(
            Receipt.id == receipt_id,
            Receipt.organization_id == org_id,
        )
        .first()
    )
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found.",
        )
    try:
        mirror = process_nsf_receipt(
            db=db,
            original=original,
            process_date=payload.process_date,
            memo=payload.memo,
            created_by=current_user,
        )
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    r = (
        db.query(Receipt)
        .options(
            joinedload(Receipt.cash_gl_account),
            joinedload(Receipt.lines).joinedload(ReceiptLine.gl_account),
        )
        .filter(Receipt.id == mirror.id)
        .first()
    )
    return _detail_out(r)


# ============================================================
# POST /api/accounting/receipts  -- create + post to GL
# ============================================================

@router.post(
    "",
    response_model=ReceiptDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_receipt(
    payload: ReceiptCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)
    if payload.type == "APPLICATION_FEE":
        _require_receipt_feature(
            db,
            current_user,
            "release.accounting.receipts.application_fee",
        )

    try:
        receipt = post_receipt(
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

    r = (
        db.query(Receipt)
        .options(
            joinedload(Receipt.cash_gl_account),
            joinedload(Receipt.lines).joinedload(ReceiptLine.gl_account),
        )
        .filter(Receipt.id == receipt.id)
        .first()
    )

    return _detail_out(r)


# ============================================================
# POST /api/accounting/receipts/{id}/reverse
# ============================================================

@router.post(
    "/{receipt_id}/reverse",
    response_model=ReceiptDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def reverse_receipt_endpoint(
    receipt_id: int,
    payload: ReceiptReverseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_receipts_access(db, current_user)

    original = (
        db.query(Receipt)
        .filter(
            Receipt.id == receipt_id,
            Receipt.organization_id == org_id,
        )
        .first()
    )
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found.",
        )

    try:
        mirror = reverse_receipt(
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

    r = (
        db.query(Receipt)
        .options(
            joinedload(Receipt.cash_gl_account),
            joinedload(Receipt.lines).joinedload(ReceiptLine.gl_account),
        )
        .filter(Receipt.id == mirror.id)
        .first()
    )

    return _detail_out(r)