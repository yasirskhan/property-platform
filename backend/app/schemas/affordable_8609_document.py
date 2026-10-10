"""Redacted Form 8609 archive metadata only, never PDF content."""
from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class Affordable8609DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    building_id: int
    size_bytes: int
    received_on: date
    uploaded_at: datetime
    uploaded_by_id: int | None
