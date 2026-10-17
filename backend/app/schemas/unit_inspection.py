"""Manual inspection record; explicitly entered evidence, not inferred status."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Condition = Literal["SATISFACTORY", "ATTENTION_NEEDED", "NOT_ASSESSED"]


class UnitInspectionCreateIn(BaseModel):
    unit_id: int = Field(ge=1)
    inspection_date: date
    recorded_condition: Condition
    findings: str = Field(default="", max_length=2000)

    @field_validator("inspection_date")
    @classmethod
    def observed_date(cls, value: date) -> date:
        if value > date.today() or value.year < 2000:
            raise ValueError("Inspection date must be a recorded past or current date")
        return value

    @field_validator("findings")
    @classmethod
    def strip_findings(cls, value: str) -> str:
        return value.strip()


class UnitInspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    unit_id: int
    inspection_date: date
    recorded_condition: Condition
    findings: str
    recorded_by_id: int | None
    recorded_at: datetime
