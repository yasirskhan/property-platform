"""Unverified staff-prepared text; never official board minutes."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAMinutesDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    staff_minutes: str = Field(min_length=1, max_length=4000)

    @field_validator("staff_minutes")
    @classmethod
    def nonblank_minutes(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Staff minutes cannot be blank")
        return text


class HOAMinutesDraftOut(BaseModel):
    id: int
    meeting_draft_id: int
    property_id: int
    staff_minutes: str
    updated_at: datetime
    status: Literal["STAFF_DRAFT_UNVERIFIED"] = "STAFF_DRAFT_UNVERIFIED"
    legal_minutes_effective: Literal[False] = False
    board_approval_certified: Literal[False] = False
    quorum_certified: Literal[False] = False
