# ============================================================
# journal_entries.py (router)
# ------------------------------------------------------------
#   GET    /api/accounting/journal-entries     list (JEs only)
#   POST   /api/accounting/journal-entries     create + post
#
# The POST endpoint is the public "create a transaction" API
# that was deferred from Step 2. It routes through
# post_transaction(transaction_type="JOURNAL_ENTRY").
#
# Reading a single JE uses the existing gl-transactions detail
# route (source_type is "manual_je" for JEs created here).
# ============================================================

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.gl_transaction import GLTransaction
from app.schemas.gl_transaction import PostingLine
from app.schemas.journal_entry import (
    JournalEntryCreateIn,
    JournalEntryOut,
    JournalEntryListOut,
)
from app.services.gl_posting import PostingError, post_transaction


router = APIRouter(
    prefix="/api/accounting/journal-entries",
    tags=["Journal Entries"],
)


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _txn_to_out(t: GLTransaction) -> JournalEntryOut:
    return JournalEntryOut(
        id=t.id,
        organization_id=t.organization_id,
        transaction_date=t.transaction_date,
        posted_at=t.posted_at,
        transaction_type=t.transaction_type,
        reference_number=t.reference_number,
        memo=t.memo,
        source_type=t.source_type,
        source_id=t.source_id,
        created_by_id=t.created_by_id,
        is_reversed=t.is_reversed,
        reversal_of_id=t.reversal_of_id,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


# ============================================================
# GET "" — list manual journal entries
# ============================================================

@router.get("", response_model=JournalEntryListOut)
def list_journal_entries(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    include_reversed: bool = Query(True),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    q = (
        db.query(GLTransaction)
        .filter(GLTransaction.organization_id == org_id)
        .filter(GLTransaction.transaction_type == "JOURNAL_ENTRY")
    )
    if date_from is not None:
        q = q.filter(GLTransaction.transaction_date >= date_from)
    if date_to is not None:
        q = q.filter(GLTransaction.transaction_date <= date_to)
    if not include_reversed:
        q = q.filter(GLTransaction.is_reversed.is_(False))

    total = q.count()
    rows = (
        q.order_by(
            GLTransaction.transaction_date.desc(),
            GLTransaction.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return JournalEntryListOut(
        items=[_txn_to_out(t) for t in rows],
        total=total,
    )


# ============================================================
# POST "" — create + post a manual JE
# ============================================================

@router.post(
    "",
    response_model=JournalEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_journal_entry(
    payload: JournalEntryCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    # Convert schema lines into PostingLine objects
    posting_lines = [
        PostingLine(
            gl_account_id=ln.gl_account_id,
            property_id=ln.property_id,
            unit_id=ln.unit_id,
            owner_id=ln.owner_id,
            description=ln.description,
            debit=ln.debit,
            credit=ln.credit,
        )
        for ln in payload.lines
    ]

    try:
        txn = post_transaction(
            db=db,
            organization_id=org_id,
            transaction_date=payload.transaction_date,
            transaction_type="JOURNAL_ENTRY",
            memo=payload.memo,
            lines=posting_lines,
            created_by=current_user,
            reference_number=payload.reference_number,
            source_type="manual_je",
            source_id=None,
        )
    except PostingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to post journal entry: {e}",
        )

    return _txn_to_out(txn)