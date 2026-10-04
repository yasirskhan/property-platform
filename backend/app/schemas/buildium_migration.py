"""Schemas for Phase 4.14 Buildium migration foundation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BuildiumMigrationRunCreateIn(BaseModel):
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


class BuildiumMigrationRunOut(BaseModel):
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


class BuildiumPropertyResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_property_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_property_id is None:
            raise ValueError("target_property_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_property_id is not None:
            raise ValueError("target_property_id is only valid for MATCH_EXISTING")
        return self


class BuildiumPropertyDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumPropertyResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumPropertyPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_property_id: int | None = None


class BuildiumPropertyDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    skipped_inactive: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumPropertyPreviewRow]


class BuildiumPropertyCommitIn(BaseModel):
    """Commit only the exact Buildium property payload previously dry-run."""

    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumPropertyResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumPropertyCommitRow(BaseModel):
    source_id: str
    target_property_id: int
    replayed: bool


class BuildiumPropertyCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int = 0
    skipped_inactive: int
    skipped_review: int = 0
    warning_count: int
    rows: list[BuildiumPropertyCommitRow]


class BuildiumMigrationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
