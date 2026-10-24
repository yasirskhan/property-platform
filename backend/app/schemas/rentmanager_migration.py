"""Contract-gated Phase 4.16 RentManager migration run payloads."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.yardi_migration import _FORBIDDEN_SOURCE_REF_MARKERS


class RentManagerRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: int = Field(ge=1)
    source_account_ref: str = Field(min_length=1, max_length=255)

    @field_validator("source_account_ref")
    @classmethod
    def clean_source_ref(cls, value: str) -> str:
        cleaned = value.strip()
        if (not cleaned or any(k in cleaned.lower() for k in _FORBIDDEN_SOURCE_REF_MARKERS)
                or any(ch in cleaned for ch in ("{", "}", "\n", "\r"))):
            raise ValueError("Use a nonsecret source account label, not credentials or provider payload.")
        return cleaned


class RentManagerRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
