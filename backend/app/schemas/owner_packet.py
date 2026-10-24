"""Frozen owner packet preview and explicit current-recipient confirmation."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class OwnerPacketPreviewOut(BaseModel):
    statement_id: int
    owner_id: int
    recipient_email: str
    period_start: date
    period_end: date
    attachment_filenames: list[str]
    attachment_format: str = "CSV"
    cover_message: str | None
    email_enabled: bool
    review_token: str


class OwnerPacketSendIn(BaseModel):
    confirm_recipient: bool
    confirm_snapshot_reviewed: bool
    review_token: str = Field(min_length=64, max_length=64)


class OwnerPacketSendOut(BaseModel):
    sent: bool
    recipient_email: str
    filenames: list[str]
