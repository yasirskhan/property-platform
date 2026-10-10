"""Schemas for Buildium Association identity reconciliation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BuildiumAssociationResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_hoa_association_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_hoa_association_id is None:
            raise ValueError(
                "target_hoa_association_id is required for MATCH_EXISTING"
            )
        if self.action != "MATCH_EXISTING" and self.target_hoa_association_id is not None:
            raise ValueError(
                "target_hoa_association_id is only valid for MATCH_EXISTING"
            )
        return self


class BuildiumAssociationDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumAssociationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumApiAssociationDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolutions: list[BuildiumAssociationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumApiAssociationCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolutions: list[BuildiumAssociationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumAssociationPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_hoa_association_id: int | None = None


class BuildiumAssociationDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumAssociationPreviewRow]


class BuildiumAssociationCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumAssociationResolutionIn] = Field(
        default_factory=list, max_length=500
    )


class BuildiumAssociationCommitRow(BaseModel):
    source_id: str
    target_hoa_association_id: int
    replayed: bool


class BuildiumAssociationCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumAssociationCommitRow]
