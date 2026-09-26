"""Text-only letter input and safely rendered tenant correspondence."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LetterTemplateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: Literal["CUSTOM", "THREE_DAY_NOTICE"] = "CUSTOM"
    subject: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=12000)

    @field_validator("title", "subject", "body")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Letter field cannot be blank")
        return value.strip()


class LetterTemplateOut(LetterTemplateIn):
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LetterPreviewOut(BaseModel):
    title: str
    category: str
    subject: str
    body: str
    recipient_email: str
    tenant_id: int
    lease_id: int
    property_id: int
    legal_notice_review_required: bool


class LetterSendIn(BaseModel):
    lease_id: int = Field(ge=1)
    confirm_recipient: bool
    confirm_content_reviewed: bool
    confirm_legal_review: bool = False


class LetterSendOut(BaseModel):
    sent: bool
    recipient_email: str
