# ============================================================
# gl_transaction.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for the General Ledger API.
#
# Read-only shapes for now. The write shape (PostingLine and
# the request that wraps it) will live here too, but the
# public "create a transaction" endpoint is deferred to Step 2b
# after receipts and bills exist. The internal posting service
# uses PostingLine directly.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------
# Posting (internal — used by services/gl_posting.py)
# ------------------------------------------------------------

class PostingLine(BaseModel):
    """One debit or credit line. Exactly one of debit/credit
    must be nonzero."""
    gl_account_id: int
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")


# ------------------------------------------------------------
# Read shapes
# ------------------------------------------------------------

class GLEntryOut(BaseModel):
    id: int
    transaction_id: int
    gl_account_id: int
    gl_account_number: Optional[str] = None
    gl_account_name: Optional[str] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    description: Optional[str] = None
    debit: Decimal
    credit: Decimal

    class Config:
        from_attributes = True


class GLTransactionOut(BaseModel):
    """A transaction WITHOUT its lines. Used in list views."""
    id: int
    organization_id: int
    transaction_date: date
    posted_at: datetime
    transaction_type: str
    reference_number: Optional[str] = None
    memo: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    created_by_id: Optional[int] = None
    is_reversed: bool
    reversal_of_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GLTransactionDetailOut(GLTransactionOut):
    """A transaction WITH its lines. Used in the detail view."""
    entries: List[GLEntryOut] = []


class GLTransactionListOut(BaseModel):
    items: List[GLTransactionOut]
    total: int


# ------------------------------------------------------------
# Ledger (entries for one account, with running balance)
# ------------------------------------------------------------

class LedgerLineOut(BaseModel):
    """One row in an account's ledger. Includes the running
    balance AFTER this line."""
    entry_id: int
    transaction_id: int
    transaction_date: date
    transaction_type: str
    reference_number: Optional[str] = None
    memo: Optional[str] = None
    description: Optional[str] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class LedgerOut(BaseModel):
    gl_account_id: int
    gl_number: str
    name: str
    account_type: str
    opening_balance: Decimal
    closing_balance: Decimal
    lines: List[LedgerLineOut]


# ------------------------------------------------------------
# Balance + Trial Balance
# ------------------------------------------------------------

class GLAccountBalanceOut(BaseModel):
    gl_account_id: int
    gl_number: str
    name: str
    account_type: str
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal


class TrialBalanceRowOut(BaseModel):
    gl_account_id: int
    gl_number: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal


class TrialBalanceOut(BaseModel):
    as_of: date
    rows: List[TrialBalanceRowOut]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool