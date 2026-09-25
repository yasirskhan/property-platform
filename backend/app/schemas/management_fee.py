# ============================================================
# management_fee.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for the Management Fees API.
#
# Preview: read-only calculation for the UI.
# Run: actually posts the fee to the GL.
# Reverse: undoes a posted fee.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# WRITE SHAPES
# ============================================================

class FeePreviewIn(BaseModel):
    """Request body for POST /api/accounting/management-fees/preview."""
    property_id: int
    period_start: date
    period_end: date


class FeeRunIn(BaseModel):
    """Request body for POST /api/accounting/management-fees/run."""
    property_id: int
    period_start: date
    period_end: date
    # Optional overrides:
    expense_gl_account_id: Optional[int] = None   # default 6001
    cash_gl_account_id: Optional[int] = None      # default 1150
    notes: Optional[str] = None

    @field_validator("period_end")
    @classmethod
    def _end_after_start(cls, v: date, info) -> date:
        start = info.data.get("period_start")
        if start is not None and v < start:
            raise ValueError("period_end must be on or after period_start")
        return v


class FeeReverseIn(BaseModel):
    reversal_date: date
    memo: Optional[str] = None


OvercollectionStrategy = Literal[
    "CREDITS_THEN_RECEIPTS",
    "RECEIPTS_THEN_CREDITS",
]


class OvercollectionStrategyUpdate(BaseModel):
    strategy: OvercollectionStrategy


class OvercollectionStrategyOut(BaseModel):
    strategy: OvercollectionStrategy
    label: str
    recommended: bool


# ============================================================
# READ SHAPES
# ============================================================

class EligibleIncomeLine(BaseModel):
    """One contributing income line in the preview."""
    receipt_id: Optional[int] = None
    transaction_id: Optional[int] = None
    transaction_date: Optional[date] = None
    gl_account_id: int
    gl_account_number: Optional[str] = None
    gl_account_name: Optional[str] = None
    amount: Decimal


class FeePreviewOut(BaseModel):
    """Read-only preview of what would be charged."""
    property_id: int
    property_name: Optional[str] = None
    period_start: date
    period_end: date

    rent_income_total: Decimal
    other_fee_income_total: Decimal

    rent_fee_pct: Decimal
    other_fee_pct: Decimal

    rent_fee_amount: Decimal
    other_fee_amount: Decimal
    total_fee: Decimal

    rent_lines: List[EligibleIncomeLine] = []
    other_lines: List[EligibleIncomeLine] = []

    can_run: bool
    reason: Optional[str] = None


class ManagementFeeRunOut(BaseModel):
    id: int
    organization_id: int
    property_id: int
    property_name: Optional[str] = None

    period_start: date
    period_end: date

    rent_income_total: Decimal
    other_fee_income_total: Decimal
    rent_fee_pct: Decimal
    other_fee_pct: Decimal
    rent_fee_amount: Decimal
    other_fee_amount: Decimal
    total_fee: Decimal

    expense_gl_account_id: int
    expense_gl_account_number: Optional[str] = None
    expense_gl_account_name: Optional[str] = None

    cash_gl_account_id: int
    cash_gl_account_number: Optional[str] = None
    cash_gl_account_name: Optional[str] = None

    gl_transaction_id: Optional[int] = None
    notes: Optional[str] = None
    is_reversed: bool
    reversal_of_id: Optional[int] = None
    is_active: bool
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ManagementFeeRunListOut(BaseModel):
    items: List[ManagementFeeRunOut]
    total: int