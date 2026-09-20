# ============================================================
# journal_entry.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for Manual Journal Entries.
#
# This is the public "create a transaction" endpoint that was
# deferred from Step 2. It uses the same validation rules as
# post_transaction() but wraps them in a manager-friendly
# request shape.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# WRITE SHAPES
# ============================================================

class JournalEntryLineIn(BaseModel):
    """One line of a manual JE. Exactly one of debit/credit
    must be > 0."""
    gl_account_id: int
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    owner_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

    @field_validator("debit", "credit")
    @classmethod
    def _non_negative(cls, v: Decimal) -> Decimal:
        if v is None:
            return Decimal("0")
        if v < 0:
            raise ValueError("debit and credit must be >= 0")
        return v


class JournalEntryCreateIn(BaseModel):
    """Request body for POST /api/accounting/journal-entries."""
    transaction_date: date
    reference_number: Optional[str] = Field(None, max_length=60)
    memo: Optional[str] = None
    lines: List[JournalEntryLineIn] = Field(..., min_length=2)

    @field_validator("lines")
    @classmethod
    def _validate_balance(
        cls, v: List[JournalEntryLineIn]
    ) -> List[JournalEntryLineIn]:
        total_debit = sum((ln.debit or Decimal("0")) for ln in v)
        total_credit = sum((ln.credit or Decimal("0")) for ln in v)

        if total_debit == 0 and total_credit == 0:
            raise ValueError("At least one line must have a debit or credit.")

        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(
                f"Journal entry does not balance: "
                f"debits={total_debit} credits={total_credit}."
            )
        return v


# ============================================================
# READ SHAPES
# ============================================================

class JournalEntryOut(BaseModel):
    """Thin wrapper — mirrors what /gl-transactions/{id} returns
    but with a friendlier name."""
    id: int
    organization_id: int
    transaction_date: date
    posted_at: Optional[datetime] = None
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


class JournalEntryListOut(BaseModel):
    items: List[JournalEntryOut]
    total: int