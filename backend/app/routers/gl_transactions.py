# ============================================================
# gl_transactions.py (router)
# ------------------------------------------------------------
# Read-only endpoints for the General Ledger.
#
#   GET /api/accounting/gl-transactions            list (filterable)
#   GET /api/accounting/gl-transactions/{id}       one + its lines
#
# Writing to the ledger is NOT exposed here. Only the internal
# posting service writes. The public "create a transaction"
# endpoint (for manual journal entries) comes in Step 2b.
#
# As of Step 8a, GLEntryOut includes owner_id so the trust
# sub-ledger and diagnostics can group GL activity by owner.
# ============================================================

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.gl_transaction import GLTransaction
from app.models.gl_entry import GLEntry
from app.schemas.gl_transaction import (
    GLTransactionOut,
    GLTransactionDetailOut,
    GLTransactionListOut,
    GLEntryOut,
)

router = APIRouter(
    prefix="/api/accounting/gl-transactions",
    tags=["GL Transactions"],
)


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


# ============================================================
# GET /api/accounting/gl-transactions  — list, filterable
# ============================================================

@router.get("", response_model=GLTransactionListOut)
def list_transactions(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    transaction_type: Optional[str] = Query(None),
    property_id: Optional[int] = Query(None),
    source_type: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    q = (
        db.query(GLTransaction)
        .filter(GLTransaction.organization_id == org_id)
    )

    if date_from is not None:
        q = q.filter(GLTransaction.transaction_date >= date_from)
    if date_to is not None:
        q = q.filter(GLTransaction.transaction_date <= date_to)
    if transaction_type is not None:
        q = q.filter(
            GLTransaction.transaction_type == transaction_type.upper()
        )
    if source_type is not None:
        q = q.filter(GLTransaction.source_type == source_type)
    if source_id is not None:
        q = q.filter(GLTransaction.source_id == source_id)

    if property_id is not None:
        # A transaction is "on" a property if any of its entries
        # reference that property.
        subq = (
            db.query(GLEntry.transaction_id)
            .filter(
                GLEntry.organization_id == org_id,
                GLEntry.property_id == property_id,
            )
            .subquery()
        )
        q = q.filter(GLTransaction.id.in_(subq))

    total = q.count()

    rows = (
        q.order_by(
            GLTransaction.transaction_date.desc(),
            GLTransaction.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return GLTransactionListOut(
        items=[GLTransactionOut.model_validate(r) for r in rows],
        total=total,
    )


# ============================================================
# GET /api/accounting/gl-transactions/{id}  — one + its lines
# ============================================================

@router.get("/{transaction_id}", response_model=GLTransactionDetailOut)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    txn = (
        db.query(GLTransaction)
        .options(
            joinedload(GLTransaction.entries).joinedload(GLEntry.gl_account)
        )
        .filter(
            GLTransaction.id == transaction_id,
            GLTransaction.organization_id == org_id,
        )
        .first()
    )
    if txn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found.",
        )

    entries_out: List[GLEntryOut] = []
    for e in txn.entries:
        entries_out.append(
            GLEntryOut(
                id=e.id,
                transaction_id=e.transaction_id,
                gl_account_id=e.gl_account_id,
                gl_account_number=e.gl_account.gl_number if e.gl_account else None,
                gl_account_name=e.gl_account.name if e.gl_account else None,
                property_id=e.property_id,
                unit_id=e.unit_id,
                owner_id=e.owner_id,
                description=e.description,
                debit=e.debit,
                credit=e.credit,
            )
        )

    return GLTransactionDetailOut(
        id=txn.id,
        organization_id=txn.organization_id,
        transaction_date=txn.transaction_date,
        posted_at=txn.posted_at,
        transaction_type=txn.transaction_type,
        reference_number=txn.reference_number,
        memo=txn.memo,
        source_type=txn.source_type,
        source_id=txn.source_id,
        created_by_id=txn.created_by_id,
        is_reversed=txn.is_reversed,
        reversal_of_id=txn.reversal_of_id,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
        entries=entries_out,
    )