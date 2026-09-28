"""Bounded, text-only lease drafts. No signatures or tenant delivery."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class TemplateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=12000)
    property_id: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("Name required")
        return result


class AddendumIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=12000)
    position: int = Field(default=0, ge=0, le=1000)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("Name required")
        return result


class AddendumOut(AddendumIn):
    id: int
    template_id: int
    created_at: datetime
    updated_at: datetime


class TemplateOut(TemplateIn):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime
    addenda: list[AddendumOut] = Field(default_factory=list)
