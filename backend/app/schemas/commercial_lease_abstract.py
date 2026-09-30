"""Read-only lease links plus explicitly staff-recorded commencement metadata."""
from __future__ import annotations
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CommercialLeaseAbstractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: int = Field(ge=1)
    source_attachment_id: int | None = Field(default=None, ge=1)
    rent_commencement_on: date | None = None


class CommercialLeaseAbstractUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rent_commencement_on: date | None = None
    source_attachment_id: int | None = Field(default=None, ge=1)


class CommercialLeaseCandidateOut(BaseModel):
    lease_id: int
    unit_id: int
    unit_number: str
    lease_start_on: date
    lease_end_on: date
    lease_status: str


class CommercialLeaseSourceOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    source_status: Literal["PRIVATE_STAFF_ATTACHMENT"] = "PRIVATE_STAFF_ATTACHMENT"


class CommercialLeaseAbstractOut(CommercialLeaseCandidateOut):
    id: int
    property_id: int
    rent_commencement_on: date | None
    source_attachment_id: int | None = None
    source_filename: str | None = None
    source_status: Literal["STAFF_LINKED_UNVERIFIED"] | None = None
    reference_status: str = "STAFF_RECORDED_UNVERIFIED"
    recorded_at: datetime
