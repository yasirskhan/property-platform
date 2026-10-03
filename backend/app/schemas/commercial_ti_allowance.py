"""Commercial TI allowance utilization tracking shapes."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CommercialTIAllowanceUseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_attachment_id: int = Field(ge=1)
    incurred_on: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    note: str = Field(min_length=5, max_length=1000)
    request_key: str = Field(min_length=8, max_length=96)


class CommercialTIAllowanceVoidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voided_on: date
    reason: str = Field(min_length=5, max_length=1000)


class CommercialTIAllowanceEvidenceOut(BaseModel):
    id: int
    filename: str
    target_type: Literal["properties", "leases"]


class CommercialTIAllowanceSummaryOut(BaseModel):
    allowance_total: Decimal
    used_active: Decimal
    remaining: Decimal
    terms_id: int


class CommercialTIAllowanceUseOut(BaseModel):
    id: int
    property_id: int
    unit_id: int
    lease_id: int
    abstract_id: int
    terms_id: int
    tenant_user_id: int
    evidence_attachment_id: int
    incurred_on: date
    amount: Decimal
    allowance_total: Decimal
    remaining_after: Decimal
    note: str
    status: Literal["ACTIVE", "VOIDED"]
    voided_on: date | None
    void_reason: str | None
    created_at: datetime
