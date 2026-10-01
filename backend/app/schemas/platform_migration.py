"""Schemas for platform-run AppFolio migration dry runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppFolioMigrationRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int = Field(ge=1)
    source_account_ref: str = Field(min_length=1, max_length=255)

    @field_validator("source_account_ref")
    @classmethod
    def clean_source_ref(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source_account_ref is required")
        return cleaned


class AppFolioMigrationRunOut(BaseModel):
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


class AppFolioPropertyDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_hidden: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class AppFolioPropertyPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)


class AppFolioPropertyDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    skipped_hidden: int
    invalid: int
    warning_count: int
    rows: list[AppFolioPropertyPreviewRow]



class AppFolioPropertyCommitIn(BaseModel):
    """Commit only the exact property payload that was previously dry-run."""

    model_config = ConfigDict(extra="forbid")

    include_hidden: bool = False
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class AppFolioPropertyCommitRow(BaseModel):
    source_id: str
    target_property_id: int
    replayed: bool


class AppFolioPropertyCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    committed: int
    skipped_hidden: int
    warning_count: int
    rows: list[AppFolioPropertyCommitRow]



class AppFolioMigrationItemOut(BaseModel):
    id: int
    run_id: int
    organization_id: int
    provider: str
    resource: str
    source_id: str
    target_entity: str
    target_id: int
    target_exists: bool
    target_label: str | None
    source_fingerprint: str
    created_by_platform_user_id: int | None
    created_at: datetime
