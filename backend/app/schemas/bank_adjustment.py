from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BankAdjustmentCreateIn(BaseModel):
    adjustment_date: date
    direction: Literal["INCREASE", "DECREASE"]
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    offset_gl_account_id: int
    reference_number: Optional[str] = Field(None, max_length=40)
    memo: Optional[str] = Field(None, max_length=500)


class BankAdjustmentReverseIn(BaseModel):
    reversal_date: date
    memo: Optional[str] = Field(None, max_length=500)


class BankAdjustmentOut(BaseModel):
    id: int
    bank_account_id: int
    bank_account_name: str
    transaction_date: date
    posted_at: datetime
    direction: Literal["INCREASE", "DECREASE"]
    amount: Decimal
    signed_amount: Decimal
    offset_gl_account_id: int
    offset_gl_account_number: Optional[str] = None
    offset_gl_account_name: Optional[str] = None
    reference_number: Optional[str] = None
    memo: Optional[str] = None
    is_reversed: bool
    created_by_id: Optional[int] = None


class BankAdjustmentListOut(BaseModel):
    items: list[BankAdjustmentOut]
    total: int
