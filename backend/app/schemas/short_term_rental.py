"""Phase 4.12 short-term-rental channel reference schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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


class ShortTermRentalNightlyPriceIn(BaseModel):
    unit_id: int = Field(gt=0)
    night_date: date
    nightly_rate: Decimal = Field(ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    minimum_stay_nights: int = Field(default=1, ge=1, le=365)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes")
    @classmethod
    def trim_price_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ShortTermRentalNightlyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    unit_id: int
    night_date: date
    nightly_rate: Decimal
    minimum_stay_nights: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


TurnoverStatus = Literal["SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


class ShortTermRentalTurnoverIn(BaseModel):
    unit_id: int = Field(gt=0)
    scheduled_start: datetime
    scheduled_end: datetime
    status: TurnoverStatus = "SCHEDULED"
    cleaning_work_order_id: int | None = Field(default=None, gt=0)
    inspection_record_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes")
    @classmethod
    def trim_turnover_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("scheduled_end")
    @classmethod
    def validate_turnover_window(cls, value: datetime, info):
        start = info.data.get("scheduled_start")
        if start is not None and value <= start:
            raise ValueError("Turnover end must be after the start.")
        return value


class ShortTermRentalTurnoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    unit_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    status: TurnoverStatus
    cleaning_work_order_id: int | None
    inspection_record_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
