"""HOA rules are staff-entered and unverified; inputs never issue legal actions."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAProcedurePolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    jurisdiction_state: str | None = Field(default=None, max_length=64)
    jurisdiction_locality: str | None = Field(default=None, max_length=160)
    notice_preparation_days: int | None = Field(default=None, ge=0, le=366)
    cure_preparation_days: int | None = Field(default=None, ge=0, le=366)
    hearing_request_days: int | None = Field(default=None, ge=0, le=366)
    proposed_fine_cap: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    draft_notice_text: str | None = Field(default=None, max_length=4000)
    supporting_evidence_id: int | None = Field(default=None, ge=1)

    @field_validator("jurisdiction_state", "jurisdiction_locality", "draft_notice_text")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class HOAProcedurePolicyOut(HOAProcedurePolicyIn):
    id: int
    association_id: int
    revision: int
    status: Literal["STAFF_CONFIGURED_UNVERIFIED"] = "STAFF_CONFIGURED_UNVERIFIED"
    issuance_enabled: Literal[False] = False
    updated_at: datetime
