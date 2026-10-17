"""Validated universal tag names. Never expose target record contents."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Tag name cannot be blank.")
        return clean


class TagUpdate(TagCreate):
    pass


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    created_at: datetime


class TagListOut(BaseModel):
    items: list[TagOut]
    total: int
