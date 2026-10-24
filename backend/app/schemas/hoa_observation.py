"""Staff observations are not an adjudicated violation or legal notice."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=240)
    observed_on: date
    details: str | None = Field(default=None, max_length=1000)

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("Staff summary required")
        return clean

    @field_validator("observed_on")
    @classmethod
    def past_observation(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Staff observation cannot be dated in the future")
        return value

    @field_validator("details")
    @classmethod
    def clean_details(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class HOAObservationOut(HOAObservationIn):
    id: int
    association_id: int
    status: Literal["STAFF_RECORDED"] = "STAFF_RECORDED"
    updated_at: datetime
