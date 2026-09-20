# ============================================================
# bill.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for the Bills API.
#
# Two-step accrual flow:
#   POST /api/accounting/bills           -> enter a bill
#   POST /api/accounting/bills/{id}/pay  -> pay a bill
#
# All money fields are Decimal. All dates are Python date.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# WRITE SHAPES
# ============================================================

class BillLineIn(BaseModel):
    """One line of a bill: which expense account, what for,
    how much."""
    gl_account_id: int
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    amount: Decimal = Field(..., gt=0)


class BillCreateIn(BaseModel):
    """Request body for POST /api/accounting/bills."""
    payee_name: str = Field(..., min_length=1, max_length=200)
    payee_user_id: Optional[int] = None

    bill_date: date
    due_date: Optional[date] = None
    reference_number: Optional[str] = Field(None, max_length=60)
    bill_number: Optional[str] = Field(None, max_length=40)

    # Payable account (defaults to 2100 Accounts Payable).
    # If not sent, the service picks 2100.
    payable_gl_account_id: Optional[int] = None

    property_id: Optional[int] = None
    unit_id: Optional[int] = None

    remarks: Optional[str] = None
    notes: Optional[str] = None

    # Source (if converting from a WO, etc.) — optional.
    source_type: Optional[str] = Field(None, max_length=40)
    source_id: Optional[int] = None

    lines: List[BillLineIn] = Field(..., min_length=1)


class BillPayIn(BaseModel):
    """Request body for POST /api/accounting/bills/{id}/pay.

    Payment posts: DR Accounts Payable / CR Cash.
    Can be partial (pay less than the bill amount).
    """
    payment_date: date
    cash_gl_account_id: int
    amount: Decimal = Field(..., gt=0)
    reference_number: Optional[str] = Field(None, max_length=60)
    remarks: Optional[str] = None


class BillReverseIn(BaseModel):
    """Request body for POST /api/accounting/bills/{id}/reverse."""
    reversal_date: date
    memo: Optional[str] = None


# ============================================================
# READ SHAPES
# ============================================================

class BillLineOut(BaseModel):
    id: int
    bill_id: int
    gl_account_id: int
    gl_account_number: Optional[str] = None
    gl_account_name: Optional[str] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    description: Optional[str] = None
    amount: Decimal

    class Config:
        from_attributes = True


class BillOut(BaseModel):
    """A bill WITHOUT its lines. Used in list views."""
    id: int
    organization_id: int

    bill_number: Optional[str] = None
    payee_name: str
    payee_user_id: Optional[int] = None

    bill_date: date
    due_date: Optional[date] = None
    reference_number: Optional[str] = None

    amount: Decimal
    amount_paid: Decimal
    status: str

    property_id: Optional[int] = None
    unit_id: Optional[int] = None

    payable_gl_account_id: int
    payable_gl_account_number: Optional[str] = None
    payable_gl_account_name: Optional[str] = None

    remarks: Optional[str] = None
    notes: Optional[str] = None

    source_type: Optional[str] = None
    source_id: Optional[int] = None

    gl_transaction_id: Optional[int] = None
    is_reversed: bool
    reversal_of_id: Optional[int] = None
    is_active: bool

    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BillDetailOut(BillOut):
    """A bill WITH its lines. Used in the detail view."""
    lines: List[BillLineOut] = []


class BillListOut(BaseModel):
    items: List[BillOut]
    total: int