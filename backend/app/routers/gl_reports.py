# ============================================================
# gl_reports.py (router)
# ------------------------------------------------------------
# Read-only reporting endpoints over the General Ledger.
#
#   GET /api/accounting/gl-accounts/{id}/ledger     full ledger for one account
#   GET /api/accounting/gl-accounts/{id}/balance    just the balance
#   GET /api/accounting/reports/trial-balance       all accounts + balances
#
# Balance rule: balance = SUM(debit) - SUM(credit). This is
# the natural balance for ASSET and EXPENSE accounts. For
# LIABILITY and INCOME accounts, the natural balance is the
# opposite sign, but we still return debit-minus-credit here
# so the client can format it as needed.
#
# Everything is scoped to the caller's org.
#
# As of Step 8a, LedgerLineOut includes owner_id so trust
# sub-ledger reporting can drill into the owner dimension.
# ============================================================

from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.gl_entry import GLEntry
from app.schemas.gl_transaction import (
    LedgerOut,
    LedgerLineOut,
    GLAccountBalanceOut,
    TrialBalanceOut,
    TrialBalanceRowOut,
)

router = APIRouter(prefix="/api/accounting", tags=["GL Reports"])


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _fetch_account_or_404(
    db: Session, org_id: int, account_id: int
) -> GLAccount:
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
# GET /api/accounting/gl-accounts/{id}/ledger
# ============================================================

@router.get("/gl-accounts/{account_id}/ledger", response_model=LedgerOut)
def get_account_ledger(
    account_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    property_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    acct = _fetch_account_or_404(db, org_id, account_id)

    # ---- opening balance (entries strictly before date_from) ----
    opening = Decimal("0")
    if date_from is not None:
        row = (
            db.query(
                func.coalesce(func.sum(GLEntry.debit), 0),
                func.coalesce(func.sum(GLEntry.credit), 0),
            )
            .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
            .filter(
                GLEntry.organization_id == org_id,
                GLEntry.gl_account_id == account_id,
                GLTransaction.transaction_date < date_from,
            )
            .one()
        )
        opening = Decimal(row[0] or 0) - Decimal(row[1] or 0)

    # ---- window query ----
    q = (
        db.query(GLEntry, GLTransaction)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(
            GLEntry.organization_id == org_id,
            GLEntry.gl_account_id == account_id,
        )
    )
    if date_from is not None:
        q = q.filter(GLTransaction.transaction_date >= date_from)
    if date_to is not None:
        q = q.filter(GLTransaction.transaction_date <= date_to)
    if property_id is not None:
        q = q.filter(GLEntry.property_id == property_id)

    rows = q.order_by(
        GLTransaction.transaction_date.asc(),
        GLTransaction.id.asc(),
        GLEntry.id.asc(),
    ).all()

    running = opening
    lines: List[LedgerLineOut] = []
    for entry, txn in rows:
        d = Decimal(entry.debit or 0)
        c = Decimal(entry.credit or 0)
        running = running + d - c
        lines.append(
            LedgerLineOut(
                entry_id=entry.id,
                transaction_id=txn.id,
                transaction_date=txn.transaction_date,
                transaction_type=txn.transaction_type,
                reference_number=txn.reference_number,
                memo=txn.memo,
                description=entry.description,
                property_id=entry.property_id,
                unit_id=entry.unit_id,
                owner_id=entry.owner_id,
                debit=d,
                credit=c,
                running_balance=running,
            )
        )

    return LedgerOut(
        gl_account_id=acct.id,
        gl_number=acct.gl_number,
        name=acct.name,
        account_type=acct.account_type,
        opening_balance=opening,
        closing_balance=running,
        lines=lines,
    )


# ============================================================
# GET /api/accounting/gl-accounts/{id}/balance
# ============================================================

@router.get("/gl-accounts/{account_id}/balance", response_model=GLAccountBalanceOut)
def get_account_balance(
    account_id: int,
    as_of: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    acct = _fetch_account_or_404(db, org_id, account_id)

    q = (
        db.query(
            func.coalesce(func.sum(GLEntry.debit), 0),
            func.coalesce(func.sum(GLEntry.credit), 0),
        )
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(
            GLEntry.organization_id == org_id,
            GLEntry.gl_account_id == account_id,
        )
    )
    if as_of is not None:
        q = q.filter(GLTransaction.transaction_date <= as_of)

    debit_total, credit_total = q.one()
    debit_total = Decimal(debit_total or 0)
    credit_total = Decimal(credit_total or 0)

    return GLAccountBalanceOut(
        gl_account_id=acct.id,
        gl_number=acct.gl_number,
        name=acct.name,
        account_type=acct.account_type,
        debit_total=debit_total,
        credit_total=credit_total,
        balance=debit_total - credit_total,
    )


# ============================================================
# GET /api/accounting/reports/trial-balance
# ============================================================

@router.get("/reports/trial-balance", response_model=TrialBalanceOut)
def get_trial_balance(
    as_of: Optional[date] = Query(None),
    include_zero: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    # Aggregate per account
    q = (
        db.query(
            GLEntry.gl_account_id,
            func.coalesce(func.sum(GLEntry.debit), 0).label("debits"),
            func.coalesce(func.sum(GLEntry.credit), 0).label("credits"),
        )
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(GLEntry.organization_id == org_id)
    )
    if as_of is not None:
        q = q.filter(GLTransaction.transaction_date <= as_of)

    agg = {
        row.gl_account_id: (Decimal(row.debits or 0), Decimal(row.credits or 0))
        for row in q.group_by(GLEntry.gl_account_id).all()
    }

    accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == org_id,
            GLAccount.is_active.is_(True),
        )
        .order_by(GLAccount.gl_number.asc())
        .all()
    )

    rows: List[TrialBalanceRowOut] = []
    total_debits = Decimal("0")
    total_credits = Decimal("0")

    for acct in accounts:
        debits, credits = agg.get(acct.id, (Decimal("0"), Decimal("0")))
        if not include_zero and debits == 0 and credits == 0:
            continue
        rows.append(
            TrialBalanceRowOut(
                gl_account_id=acct.id,
                gl_number=acct.gl_number,
                name=acct.name,
                account_type=acct.account_type,
                debit=debits,
                credit=credits,
            )
        )
        total_debits += debits
        total_credits += credits

    return TrialBalanceOut(
        as_of=as_of or date.today(),
        rows=rows,
        total_debits=total_debits,
        total_credits=total_credits,
        is_balanced=abs(total_debits - total_credits) <= Decimal("0.01"),
    )