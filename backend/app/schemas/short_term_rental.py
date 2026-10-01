"""Phase 4.12 short-term-rental channel reference schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ChannelProvider = Literal["AIRBNB", "VRBO"]


class ShortTermRentalChannelIn(BaseModel):
    provider: ChannelProvider
    label: str = Field(min_length=1, max_length=120)
    external_listing_id: str | None = Field(default=None, max_length=180)
    public_listing_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("label", "external_listing_id", "public_listing_url", "notes")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ShortTermRentalChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    provider: ChannelProvider
    label: str
    external_listing_id: str | None
    public_listing_url: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
