"""An internal HOA case, not legal notice or fine adjudication."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CaseStage = Literal[
    "OPEN", "NOTICE_DRAFT", "CURE_TRACKING", "HEARING_PLANNED",
    "FINE_PROPOSED", "RESOLVED", "CLOSED",
]


class HOAViolationCaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    observation_id: int = Field(ge=1)


class HOAViolationAdvanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    next_stage: CaseStage
    action_on: date | None = None
    proposed_fine: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    staff_resolution: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def fields_match_transition(self):
        if self.next_stage in {"OPEN"}:
            raise ValueError("A case may not be reset to OPEN.")
        if self.next_stage in {"NOTICE_DRAFT", "HEARING_PLANNED"}:
            if self.action_on is None:
                raise ValueError("A planned date is required.")
        elif self.action_on is not None:
            raise ValueError("A planned date is only allowed for notice/hearing preparation.")
        if (self.next_stage == "FINE_PROPOSED") != (self.proposed_fine is not None):
            raise ValueError("A proposed fine amount is only allowed at FINE_PROPOSED.")
        if (self.next_stage == "RESOLVED") != (self.staff_resolution is not None):
            raise ValueError("A staff resolution is only allowed at RESOLVED.")
        return self


class HOAViolationCaseOut(BaseModel):
    id: int
    association_id: int
    property_id: int
    observation_id: int
    stage: CaseStage
    draft_notice_on: date | None
    tentative_cure_on: date | None
    tentative_hearing_on: date | None
    proposed_fine: Decimal | None
    staff_resolution: str | None
    policy_revision: int | None
    updated_at: datetime
    notice_sent: Literal[False] = False
    fine_assessed: Literal[False] = False
    legally_adjudicated: Literal[False] = False
