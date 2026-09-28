"""HOA inventory only; no legal governing status, dues or owner liabilities."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class HOAAssociationIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    property_ids: list[int] = Field(default_factory=list, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Association name cannot be blank")
        return value

    @field_validator("property_ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        if any(id_ <= 0 for id_ in value) or len(set(value)) != len(value):
            raise ValueError("Property IDs must be positive and distinct")
        return value


class HOAAssociationOut(BaseModel):
    id: int
    name: str
    property_ids: list[int]
    updated_at: datetime



class HOAContactLinkIn(BaseModel):
    property_id: int = Field(ge=1)
    contact_id: int = Field(ge=1)


class HOAContactLinkOut(BaseModel):
    id: int
    association_id: int
    property_id: int
    contact_id: int
    contact_name: str
