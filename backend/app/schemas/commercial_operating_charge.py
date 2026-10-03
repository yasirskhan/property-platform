"""Commercial CAM/NNN accounting execution shapes."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CommercialOperatingChargeIssueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["CAM", "NNN"]
    period_start: date
    period_end: date
    posting_on: date
    due_on: date
    receivable_gl_account_id: int = Field(ge=1)
    income_gl_account_id: int = Field(ge=1)
    request_key: str = Field(min_length=8, max_length=96)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.period_end < self.period_start:
            raise ValueError("Commercial charge period end cannot precede start.")
        if self.due_on < self.posting_on:
            raise ValueError("Commercial charge due date cannot precede posting date.")
        return self


class CommercialOperatingChargeReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reversal_on: date
    reason: str = Field(min_length=5, max_length=1000)


class CommercialOperatingChargeOut(BaseModel):
    id: int
    property_id: int
    unit_id: int
    lease_id: int
    abstract_id: int
    terms_id: int
    tenant_user_id: int
    kind: Literal["CAM", "NNN"]
    period_start: date
    period_end: date
    posting_on: date
    due_on: date
    cam_amount: Decimal
    tax_amount: Decimal
    insurance_amount: Decimal
    total_amount: Decimal
    receivable_gl_account_id: int
    income_gl_account_id: int
    charge_id: int
    gl_transaction_id: int
    reversal_transaction_id: int | None
    status: Literal["POSTED", "REVERSED"]
    reversal_on: date | None
    reversal_reason: str | None
    created_at: datetime


class CommercialGLAccountOptionOut(BaseModel):
    id: int
    gl_number: str
    name: str
    account_type: Literal["ASSET", "INCOME"]
