from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")


class MySettingsUpdate(BaseModel):
    email_notifications_enabled: bool = True
    email_signature: Optional[str] = Field(default=None, max_length=2000)
    reply_to_email: Optional[EmailStr] = None
    language_override: Optional[str] = Field(default=None, max_length=16)
    export_format_override: Optional[str] = None

    @field_validator("email_signature", mode="before")
    @classmethod
    def normalize_signature(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("language_override", mode="before")
    @classmethod
    def normalize_language(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not _LANGUAGE_RE.fullmatch(text):
            raise ValueError("language_override must be a language code such as en or en-US")
        return text

    @field_validator("export_format_override", mode="before")
    @classmethod
    def normalize_export_format(cls, value):
        if value is None:
            return None
        normalized = str(value).strip().upper()
        if not normalized:
            return None
        if normalized not in {"CSV", "EXCEL"}:
            raise ValueError("export_format_override must be CSV or EXCEL")
        return normalized


class MySettingsOut(MySettingsUpdate):
    user_id: int
    organization_id: int
