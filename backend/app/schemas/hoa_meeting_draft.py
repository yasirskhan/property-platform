"""Planning metadata only; deliberately no legal or governance fields."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAMeetingDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=140)
    proposed_on: date
    staff_agenda: str | None = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Staff meeting plan title required")
        return cleaned

    @field_validator("staff_agenda")
    @classmethod
    def clean_agenda(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class HOAMeetingDraftOut(HOAMeetingDraftIn):
    id: int
    association_id: int
    status: Literal["STAFF_DRAFT"] = "STAFF_DRAFT"
    updated_at: datetime
