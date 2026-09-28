"""No approval, issuance, owner/tenant payer, due date or posting can be supplied."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HOAAssessmentProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    assessment_type: Literal["RECURRING", "SPECIAL"]
    frequency: Literal["MONTHLY", "QUARTERLY", "ANNUAL", "ONE_TIME"]
    proposed_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    proposed_first_on: date
    proposed_through: date | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name:
            raise ValueError("Title cannot be blank")
        return name

    @model_validator(mode="after")
    def proposal_only(self):
        if self.assessment_type == "SPECIAL" and self.frequency != "ONE_TIME":
            raise ValueError("Special assessment proposals must be ONE_TIME")
        if self.assessment_type == "RECURRING" and self.frequency == "ONE_TIME":
            raise ValueError("Recurring assessment proposals require a recurrence frequency")
        if self.proposed_through and self.proposed_through < self.proposed_first_on:
            raise ValueError("Proposed end must not precede proposed start")
        return self


class HOAAssessmentProposalOut(HOAAssessmentProposalIn):
    id: int
    association_id: int
    status: Literal["DRAFT"] = "DRAFT"
    updated_at: datetime
