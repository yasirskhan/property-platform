"""Read-only lease links plus explicitly staff-recorded commencement metadata."""
from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class CommercialLeaseAbstractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: int = Field(ge=1)
    rent_commencement_on: date | None = None


class CommercialLeaseAbstractUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rent_commencement_on: date | None = None


class CommercialLeaseCandidateOut(BaseModel):
    lease_id: int
    unit_id: int
    unit_number: str
    lease_start_on: date
    lease_end_on: date
    lease_status: str


class CommercialLeaseAbstractOut(CommercialLeaseCandidateOut):
    id: int
    property_id: int
    rent_commencement_on: date | None
    reference_status: str = "STAFF_RECORDED_UNVERIFIED"
    recorded_at: datetime
