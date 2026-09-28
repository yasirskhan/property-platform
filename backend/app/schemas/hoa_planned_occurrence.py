"""Versioned staff-only schedule history. No issued assessment or receivable."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class HOAPlanGenerationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def check_range(self):
        if self.date_to < self.date_from:
            raise ValueError("End must not precede start")
        return self


class HOAPlannedOccurrenceOut(BaseModel):
    id: int
    proposal_id: int
    property_id: int
    payer_draft_id: int
    proposed_on: date
    proposed_amount: Decimal
    proposal_revision_at: datetime
    status: Literal["PLANNED", "VOIDED"]
    created_at: datetime
    voided_at: datetime | None = None
    is_issued: Literal[False] = False
    is_receivable: Literal[False] = False
    legal_payer_verified: Literal[False] = False
    gl_posting_enabled: Literal[False] = False


class HOAPlanGenerationOut(BaseModel):
    rows: list[HOAPlannedOccurrenceOut]
    new_count: int
    existing_count: int
    status: Literal["PLANNING_ONLY"] = "PLANNING_ONLY"
