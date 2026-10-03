"""Only explicitly authorized group records and memberships."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PropertyGroupUpsertIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    property_ids: list[int] = Field(default_factory=list, max_length=500)

    @field_validator("name")
    @classmethod
    def name_nonblank(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Name is required")
        return clean

    @field_validator("property_ids")
    @classmethod
    def ids_unique(cls, value: list[int]) -> list[int]:
        if any(x <= 0 for x in value) or len(set(value)) != len(value):
            raise ValueError("Property IDs must be positive and distinct")
        return value


class PropertyGroupOut(BaseModel):
    id: int
    name: str
    description: str | None
    property_ids: list[int]
    updated_at: datetime
