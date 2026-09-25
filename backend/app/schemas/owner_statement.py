# ============================================================
# owner_statement.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for Owner Statements.
#
# Preview: computes what a statement would show (read-only).
# Generate: creates and freezes the statement.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# WRITE SHAPES
# ============================================================

class StatementPreviewIn(BaseModel):
    owner_id: int
    period_start: date
    period_end: date

    @field_validator("period_end")
    @classmethod
    def _end_after_start(cls, v: date, info) -> date:
        start = info.data.get("period_start")
        if start is not None and v < start:
            raise ValueError("period_end must be on or after period_start")
        return v


class StatementGenerateIn(StatementPreviewIn):
    notes: Optional[str] = None


# ============================================================
# READ SHAPES
# ============================================================

class StatementTransactionLine(BaseModel):
    date: str
    description: Optional[str] = None
    reference: Optional[str] = None
    income: Decimal = Decimal("0")
    expense: Decimal = Decimal("0")
    running_balance: Decimal = Decimal("0")
    gl_transaction_id: Optional[int] = None


class StatementPropertyBlock(BaseModel):
    property_id: int
    property_name: str
    ownership_pct: Decimal
    beginning_cash: Decimal
    ending_cash: Decimal
    income: Decimal
    expense: Decimal
    net: Decimal
    required_reserves: Decimal = Decimal("0")
    prepaid_rent: Decimal = Decimal("0")
    available_cash: Decimal = Decimal("0")
    transactions: List[StatementTransactionLine] = []


class StatementPreviewOut(BaseModel):
    owner_id: int
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None

    period_start: date
    period_end: date

    total_beginning_cash: Decimal
    total_ending_cash: Decimal
    total_income: Decimal
    total_expense: Decimal
    total_net: Decimal
    total_required_reserves: Decimal = Decimal("0")
    total_prepaid_rent: Decimal = Decimal("0")
    total_available_cash: Decimal = Decimal("0")

    properties: List[StatementPropertyBlock] = []

    can_generate: bool = True
    reason: Optional[str] = None


class OwnerStatementOut(BaseModel):
    id: int
    organization_id: int
    owner_id: int
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None

    period_start: date
    period_end: date
    generated_at: Optional[datetime] = None

    total_beginning_cash: Decimal
    total_ending_cash: Decimal
    total_income: Decimal
    total_expense: Decimal
    total_net: Decimal

    pdf_url: Optional[str] = None
    notes: Optional[str] = None

    is_active: bool
    generated_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OwnerStatementDetailOut(OwnerStatementOut):
    """Statement WITH the frozen property_data block expanded."""
    properties: List[StatementPropertyBlock] = []
    total_required_reserves: Decimal = Decimal("0")
    total_prepaid_rent: Decimal = Decimal("0")
    total_available_cash: Decimal = Decimal("0")


class PropertyCashSummaryLine(BaseModel):
    property_id: int
    property_name: str
    ending_cash: Decimal
    required_reserves: Decimal
    prepaid_rent: Decimal
    available_cash: Decimal


class OwnerStatementCashSummaryOut(BaseModel):
    statement_id: int
    total_ending_cash: Decimal
    total_required_reserves: Decimal
    total_prepaid_rent: Decimal
    total_available_cash: Decimal
    properties: List[PropertyCashSummaryLine] = []


class OwnerStatementListOut(BaseModel):
    items: List[OwnerStatementOut]
    total: int