# ============================================================
# deposit.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for the Bank Deposits API.
#
# Deposits tag receipts as "already deposited." They do NOT
# post to the GL — receipts already credited cash when posted.
#
# See app/services/deposit_posting.py.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# WRITE SHAPES
# ============================================================

class DepositCreateIn(BaseModel):
    """Request body for POST /api/accounting/deposits.

    Provide the bank account, deposit date, and the IDs of the
    receipts that are included in this deposit. The service
    computes the total from those receipts.
    """
    bank_gl_account_id: int
    deposit_date: date
    deposit_number: Optional[str] = Field(None, max_length=40)
    description: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    receipt_ids: List[int] = Field(..., min_length=1)

    @field_validator("receipt_ids")
    @classmethod
    def _no_dupes(cls, v: List[int]) -> List[int]:
        seen = set()
        for rid in v:
            if rid in seen:
                raise ValueError(
                    f"Receipt id {rid} appears more than once."
                )
            seen.add(rid)
        return v


# ============================================================
# READ SHAPES
# ============================================================

class DepositLineOut(BaseModel):
    id: int
    deposit_id: int
    receipt_id: int
    # Receipt summary fields for convenience in the UI:
    receipt_date: Optional[date] = None
    receipt_type: Optional[str] = None
    receipt_amount: Optional[Decimal] = None
    receipt_reference: Optional[str] = None
    receipt_payer: Optional[str] = None

    class Config:
        from_attributes = True


class DepositOut(BaseModel):
    """A deposit WITHOUT its lines. Used in list views."""
    id: int
    organization_id: int

    bank_gl_account_id: int
    bank_gl_account_number: Optional[str] = None
    bank_gl_account_name: Optional[str] = None

    deposit_date: date
    deposit_number: Optional[str] = None
    description: Optional[str] = None
    total: Decimal
    notes: Optional[str] = None

    is_active: bool

    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # How many receipts are in this deposit
    line_count: int = 0

    class Config:
        from_attributes = True


class DepositDetailOut(DepositOut):
    """A deposit WITH its lines. Used in the detail view."""
    lines: List[DepositLineOut] = []


class DepositListOut(BaseModel):
    items: List[DepositOut]
    total: int


# ============================================================
# HELPER SHAPE: un-deposited receipts picker
# ============================================================

class UndepositedReceiptRow(BaseModel):
    """One row in the receipt picker on the New Deposit page."""
    id: int
    receipt_date: date
    type: str
    amount: Decimal
    reference_number: Optional[str] = None
    cash_gl_account_id: int
    cash_gl_account_number: Optional[str] = None
    cash_gl_account_name: Optional[str] = None
    payer_label: Optional[str] = None

    class Config:
        from_attributes = True


class UndepositedReceiptsOut(BaseModel):
    items: List[UndepositedReceiptRow]
    total: int
    total_amount: Decimal