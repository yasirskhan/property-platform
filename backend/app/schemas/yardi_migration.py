"""Schemas for Phase 4.15 Yardi migration-run foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


_FORBIDDEN_SOURCE_REF_MARKERS = (
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "bearer ",
    "client_secret",
    "api_key",
    "apikey",
)


class YardiMigrationRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int = Field(ge=1)
    source_account_ref: str = Field(min_length=1, max_length=255)

    @field_validator("source_account_ref")
    @classmethod
    def clean_source_ref(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source_account_ref is required")
        lowered = cleaned.lower()
        if any(marker in lowered for marker in _FORBIDDEN_SOURCE_REF_MARKERS):
            raise ValueError("source_account_ref must not contain credentials or secret material")
        if any(ch in cleaned for ch in ("{", "}", "\n", "\r")):
            raise ValueError("source_account_ref must be a bounded account label, not a raw provider payload")
        return cleaned


class YardiMigrationRunOut(BaseModel):
    id: int
    organization_id: int
    provider: str
    source_account_ref: str
    status: str
    last_dry_run_fingerprint: str | None
    last_dry_run_summary: dict[str, Any] | None
    created_by_platform_user_id: int | None
    created_at: datetime
    updated_at: datetime
