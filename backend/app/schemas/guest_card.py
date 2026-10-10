"""Structured staff guest cards: no applicant identity, SSN or financial information."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

NextStep = Literal["NONE", "FOLLOW_UP", "APPLICATION_INVITED", "NOT_INTERESTED", "TOUR_RESCHEDULE"]

class GuestCardIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prospect_id: int = Field(ge=1)
    visit_on: date
    unit_id: int | None = Field(default=None, ge=1)
    attended: bool = False
    next_step: NextStep = "NONE"

class GuestCardUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: int | None = Field(default=None, ge=1)
    attended: bool | None = None
    next_step: NextStep | None = None

class GuestCardOut(GuestCardIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    property_id: int
    contact_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class GuestCardList(BaseModel):
    items: list[GuestCardOut]
    total: int
