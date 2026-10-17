"""Recorded affordable-housing program labels, never regulatory certification."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProgramType = Literal["SECTION_8_VOUCHER", "SECTION_8_PROJECT_BASED", "LIHTC", "HUD_OTHER", "OTHER"]


class AffordableProgramIn(BaseModel):
    program_type: ProgramType
    label: str = Field(min_length=1, max_length=120)
    agency_name: str | None = Field(default=None, max_length=160)
    recorded_start: date | None = None
    recorded_end: date | None = None

    @field_validator("label")
    @classmethod
    def label_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Program label is required")
        return value

    @field_validator("agency_name")
    @classmethod
    def agency_trim(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def period_order(self):
        if self.recorded_start and self.recorded_end and self.recorded_end < self.recorded_start:
            raise ValueError("Recorded end precedes start")
        return self


class AffordableProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    program_type: ProgramType
    label: str
    agency_name: str | None
    recorded_start: date | None
    recorded_end: date | None
    created_at: datetime
    updated_at: datetime
