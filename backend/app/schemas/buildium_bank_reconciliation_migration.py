"""Schemas for bounded Buildium bank-reconciliation reconciliation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BuildiumBankReconciliationResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_reconciliation_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_reconciliation_id is None:
            raise ValueError("target_reconciliation_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_reconciliation_id is not None:
            raise ValueError("target_reconciliation_id is only valid for MATCH_EXISTING")
        return self


class BuildiumBankReconciliationDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBankReconciliationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumApiBankReconciliationDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolutions: list[BuildiumBankReconciliationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumApiBankReconciliationCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolutions: list[BuildiumBankReconciliationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumBankReconciliationPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_reconciliation_id: int | None = None


class BuildiumBankReconciliationDryRunOut(BaseModel):
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
    rows: list[BuildiumBankReconciliationPreviewRow]


class BuildiumBankReconciliationCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBankReconciliationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumBankReconciliationCommitRow(BaseModel):
    source_id: str
    target_reconciliation_id: int
    replayed: bool


class BuildiumBankReconciliationCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumBankReconciliationCommitRow]
