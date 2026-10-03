"""Commercial percentage-rent annual execution shapes."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CommercialPercentageRentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reporting_year: int = Field(ge=2000, le=2200)
    evidence_attachment_id: int = Field(ge=1)
    gross_sales: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    posting_on: date
    due_on: date
    receivable_gl_account_id: int = Field(ge=1)
    income_gl_account_id: int = Field(ge=1)
    request_key: str = Field(min_length=8, max_length=96)


class CommercialPercentageRentReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reversal_on: date
    reason: str = Field(min_length=5, max_length=1000)


class CommercialPercentageRentEvidenceOut(BaseModel):
    id: int
    filename: str
    target_type: Literal["properties", "leases"]


class CommercialPercentageRentOut(BaseModel):
    id: int
    property_id: int
    unit_id: int
    lease_id: int
    abstract_id: int
    terms_id: int
    tenant_user_id: int
    evidence_attachment_id: int
    reporting_year: int
    gross_sales: Decimal
    breakpoint_annual: Decimal
    rate_percent: Decimal
    excess_sales: Decimal
    percentage_rent_due: Decimal
    posting_on: date
    due_on: date
    receivable_gl_account_id: int
    income_gl_account_id: int
    charge_id: int | None
    gl_transaction_id: int | None
    reversal_transaction_id: int | None
    status: Literal["POSTED", "ZERO", "REVERSED"]
    reversal_on: date | None
    reversal_reason: str | None
    created_at: datetime
