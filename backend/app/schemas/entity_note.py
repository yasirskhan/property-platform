from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class EntityNoteCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Note cannot be blank.")
        return clean


class EntityNoteOut(BaseModel):
    id: int
    organization_id: int
    entity_type: str
    entity_id: int
    body: str
    created_by_id: int | None = None
    created_by_name: str | None = None
    created_at: datetime


class EntityNoteListOut(BaseModel):
    items: list[EntityNoteOut]
    total: int
