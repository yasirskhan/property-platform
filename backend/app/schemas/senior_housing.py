"""Phase 4.11 recorded senior-housing age restriction schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RestrictionType = Literal["AGE_55_PLUS", "AGE_62_PLUS", "OTHER_RECORDED"]


class SeniorAgeRestrictionIn(BaseModel):
    restriction_type: RestrictionType
    label: str = Field(min_length=1, max_length=120)
    minimum_age: int | None = Field(default=None, ge=1, le=120)
    recorded_authority: str | None = Field(default=None, max_length=180)
    reference_identifier: str | None = Field(default=None, max_length=180)
    effective_start: date | None = None
    effective_end: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Restriction label is required")
        return value

    @field_validator("recorded_authority", "reference_identifier", "notes")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_record(self):
        if self.effective_start and self.effective_end and self.effective_end < self.effective_start:
            raise ValueError("Effective end precedes start")
        expected = {"AGE_55_PLUS": 55, "AGE_62_PLUS": 62}
        if self.restriction_type in expected:
            if self.minimum_age is None:
                self.minimum_age = expected[self.restriction_type]
            elif self.minimum_age != expected[self.restriction_type]:
                raise ValueError("Minimum age must match the recorded restriction type")
        return self


class SeniorAgeRestrictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    restriction_type: RestrictionType
    label: str
    minimum_age: int | None
    recorded_authority: str | None
    reference_identifier: str | None
    effective_start: date | None
    effective_end: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
