# ============================================================
# receipt.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for the Receipts API.
#
# Three sections:
#   1. Write shapes    - what the frontend POSTs to us
#   2. Read shapes     - what we send back
#   3. List wrapper    - items + total
#
# All money fields are Decimal (never float) so we never
# lose pennies. All dates are Python date objects.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# 1. WRITE SHAPES (request bodies)
# ============================================================

class ReceiptLineIn(BaseModel):
    """One line of a receipt, sent from the charges table or
    the manual line editor."""
    gl_account_id: int
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    amount_to_pay: Decimal = Field(..., ge=0)
    line_date: Optional[date] = None
    is_prepayment: bool = False

    @field_validator("amount_to_pay")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("amount_to_pay must be >= 0")
        return v


class ReceiptCreateIn(BaseModel):
    """Request body for POST /api/accounting/receipts.

    The three types share this shape. Fields not relevant to
    the type are simply left null; the service validates that
    the right fields are present for the type.
    """
    type: str  # TENANT | OWNER | OTHER

    receipt_date: date
    amount: Decimal = Field(..., gt=0)

    cash_gl_account_id: int

    # TENANT-only
    tenant_user_id: Optional[int] = None

    # OWNER-only
    owner_user_id: Optional[int] = None
    income_gl_account_id: Optional[int] = None
    payer_name: Optional[str] = Field(None, max_length=200)

    # OTHER-only
    received_from: Optional[str] = Field(None, max_length=200)
    exclude_from_mgmt_fee: bool = False

    # Common
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    reference_number: Optional[str] = Field(None, max_length=60)
    remarks: Optional[str] = None
    notes: Optional[str] = None

    # TENANT-only (and required for TENANT). For OWNER and
    # OTHER, the service derives a single line automatically
    # from income_gl_account_id, so lines may be empty here.
    lines: List[ReceiptLineIn] = []

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        up = (v or "").strip().upper()
        if up not in {"TENANT", "OWNER", "OTHER"}:
            raise ValueError("type must be TENANT, OWNER, or OTHER")
        return up


class ReceiptReverseIn(BaseModel):
    """Request body for POST /api/accounting/receipts/{id}/reverse."""
    reversal_date: date
    memo: Optional[str] = None


# ============================================================
# 2. READ SHAPES (responses)
# ============================================================

class ReceiptLineOut(BaseModel):
    id: int
    receipt_id: int
    gl_account_id: int
    gl_account_number: Optional[str] = None
    gl_account_name: Optional[str] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    description: Optional[str] = None
    amount_to_pay: Decimal
    line_date: Optional[date] = None
    is_prepayment: bool

    class Config:
        from_attributes = True


class ReceiptOut(BaseModel):
    """A receipt WITHOUT its lines. Used in list views."""
    id: int
    organization_id: int
    type: str
    receipt_date: date
    amount: Decimal

    cash_gl_account_id: int
    cash_gl_account_number: Optional[str] = None
    cash_gl_account_name: Optional[str] = None

    tenant_user_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    income_gl_account_id: Optional[int] = None
    payer_name: Optional[str] = None

    received_from: Optional[str] = None
    exclude_from_mgmt_fee: bool

    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    reference_number: Optional[str] = None
    remarks: Optional[str] = None
    notes: Optional[str] = None

    gl_transaction_id: Optional[int] = None
    is_reversed: bool
    reversal_of_id: Optional[int] = None
    is_active: bool

    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReceiptDetailOut(ReceiptOut):
    """A receipt WITH its lines. Used in the detail view."""
    lines: List[ReceiptLineOut] = []


class ReceiptListOut(BaseModel):
    items: List[ReceiptOut]
    total: int