"""Schemas for bounded Buildium full bank-deposit reconciliation."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BuildiumDepositResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_deposit_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_deposit_id is None:
            raise ValueError("target_deposit_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_deposit_id is not None:
            raise ValueError("target_deposit_id is only valid for MATCH_EXISTING")
        return self


class BuildiumDepositDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumDepositResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumApiDepositDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date
    resolutions: list[BuildiumDepositResolutionIn] = Field(
        default_factory=list, max_length=500
    )

    @model_validator(mode="after")
    def validate_date_window(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("date window must not exceed 366 days")
        return self


class BuildiumApiDepositCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolutions: list[BuildiumDepositResolutionIn] = Field(
        default_factory=list, max_length=500
    )

    @model_validator(mode="after")
    def validate_date_window(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("date window must not exceed 366 days")
        return self


class BuildiumDepositPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_deposit_id: int | None = None


class BuildiumDepositDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed: bool
    total: int
    reviewable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumDepositPreviewRow]


class BuildiumDepositCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumDepositResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumDepositCommitRow(BaseModel):
    source_id: str
    target_deposit_id: int
    replayed: bool


class BuildiumDepositCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumDepositCommitRow]
