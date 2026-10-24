"""ARC staff notes cannot encode official application or decision fields."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAARCIntakeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: int = Field(ge=1)
    project_title: str = Field(min_length=1, max_length=140)
    staff_noted_on: date
    staff_description: str | None = Field(default=None, max_length=1000)

    @field_validator("project_title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean:
            raise ValueError("Project title required")
        return clean

    @field_validator("staff_description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class HOAARCIntakeOut(HOAARCIntakeIn):
    id: int
    association_id: int
    status: Literal["STAFF_INTAKE"] = "STAFF_INTAKE"
    updated_at: datetime
