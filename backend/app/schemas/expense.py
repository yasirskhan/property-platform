# ============================================================
# schemas/expense.py
# ============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.expense import ExpenseCategory, ExpenseSource


class PropertyExpenseBase(BaseModel):
    category: ExpenseCategory = ExpenseCategory.OTHER
    amount: Decimal = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    expense_date: date
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class PropertyExpenseCreate(PropertyExpenseBase):
    pass


class PropertyExpenseUpdate(BaseModel):
    category: Optional[ExpenseCategory] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    expense_date: Optional[date] = None
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class PropertyExpenseOut(PropertyExpenseBase):
    id: int
    property_id: int
    source: ExpenseSource
    source_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True