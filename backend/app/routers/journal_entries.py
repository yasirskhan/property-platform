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
from app.models.recurring_journal_entry import RecurringJournalEntry
from app.schemas.gl_transaction import PostingLine
from app.schemas.journal_entry import (
    JournalEntryCreateIn,
    JournalEntryOut,
    JournalEntryListOut,
    RecurringJournalEntryCreateIn,
    RecurringJournalEntryListOut,
    RecurringJournalEntryOut,
    RecurringJournalEntryStatusIn,
    GPRCandidateListOut,
    GPRCandidateOut,
    GPRPostIn,
    GPRPostResultOut,
)
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction
from app.services.recurring_journal_entries import (
    create_recurring_journal_entry,
    recurring_journal_entries_enabled_for_org,
)
from app.services.menu_resolver import permission_allows_user
from app.services.gpr_posting import (
    gpr_posting_enabled_for_org,
    list_gpr_candidates,
    month_bounds,
    post_gpr,
)


router = APIRouter(
    prefix="/api/accounting/journal-entries",
    tags=["Journal Entries"],
)

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}


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


def _require_journal_entries_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.JOURNAL_ENTRIES"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Journal Entries permission required.",
        )
    return org_id


def _require_write(current_user: User) -> None:
    if _norm_role(current_user.role) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to post journal entries.",
        )


def _require_recurring_access(db: Session, current_user: User) -> int:
    org_id = _require_journal_entries_access(db, current_user)
    if not recurring_journal_entries_enabled_for_org(
        db, organization_id=org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring Journal Entries is not available.",
        )
    return org_id


def _recurring_to_out(row: RecurringJournalEntry) -> RecurringJournalEntryOut:
    return RecurringJournalEntryOut.model_validate(row)


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
# RECURRING JOURNAL ENTRIES
# ============================================================

@router.get("/recurring", response_model=RecurringJournalEntryListOut)
def list_recurring_journal_entries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_recurring_access(db, current_user)
    rows = (
        db.query(RecurringJournalEntry)
        .filter(RecurringJournalEntry.organization_id == org_id)
        .order_by(
            RecurringJournalEntry.is_active.desc(),
            RecurringJournalEntry.next_post_date.asc(),
            RecurringJournalEntry.id.asc(),
        )
        .all()
    )
    return RecurringJournalEntryListOut(
        items=[_recurring_to_out(row) for row in rows],
        total=len(rows),
    )


@router.post(
    "/recurring",
    response_model=RecurringJournalEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_recurring_journal_entry_route(
    payload: RecurringJournalEntryCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_recurring_access(db, current_user)
    try:
        row = create_recurring_journal_entry(
            db,
            organization_id=org_id,
            created_by=current_user,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            day_of_month=payload.day_of_month,
            reference_number=payload.reference_number,
            memo=payload.memo,
            lines=payload.lines,
        )
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _recurring_to_out(row)


@router.patch(
    "/recurring/{schedule_id}/status",
    response_model=RecurringJournalEntryOut,
)
def update_recurring_journal_entry_status(
    schedule_id: int,
    payload: RecurringJournalEntryStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_recurring_access(db, current_user)
    row = (
        db.query(RecurringJournalEntry)
        .filter(
            RecurringJournalEntry.id == schedule_id,
            RecurringJournalEntry.organization_id == org_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring journal entry not found.",
        )
    row.is_active = payload.is_active
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=org_id,
        entity_type="recurring_journal_entry",
        entity_id=row.id,
        action="activate" if payload.is_active else "pause",
    )
    db.commit()
    db.refresh(row)
    return _recurring_to_out(row)


# ============================================================
# GROSS POTENTIAL RENT
# ============================================================

def _require_gpr_access(db: Session, current_user: User) -> int:
    org_id = _require_journal_entries_access(db, current_user)
    if not gpr_posting_enabled_for_org(db, organization_id=org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post GPR is not available.",
        )
    return org_id


@router.get("/gpr", response_model=GPRCandidateListOut)
def get_gpr_candidates(
    month: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_gpr_access(db, current_user)
    normalized, _ = month_bounds(month)
    try:
        rows = list_gpr_candidates(db, organization_id=org_id, month=normalized)
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
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


@router.post("/gpr", response_model=GPRPostResultOut)
def post_gpr_route(
    payload: GPRPostIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_gpr_access(db, current_user)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    return GPRPostResultOut(
        month=normalized,
        posted=len(transactions),
        transaction_ids=[row.id for row in transactions],
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
    org_id = _require_journal_entries_access(db, current_user)

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
    _require_write(current_user)
    org_id = _require_journal_entries_access(db, current_user)

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