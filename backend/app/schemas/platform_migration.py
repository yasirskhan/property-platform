"""Schemas for platform-run AppFolio migration dry runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    matched_existing: int = 0
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



class AppFolioMigrationUploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    organization_id: int
    provider: str
    filename: str
    file_format: str
    file_sha256: str
    normalized_fingerprint: str
    detected_resource: str
    sheet_name: str
    headers: list[str]
    column_mapping: dict[str, str]
    validation_summary: dict[str, Any]
    status: str
    row_count: int
    created_by_platform_user_id: int | None
    created_at: datetime
    replayed: bool = False


class AppFolioMigrationStagedRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_id: int
    run_id: int
    organization_id: int
    provider: str
    resource: str
    row_number: int
    source_id: str | None
    disposition: str
    row_fingerprint: str
    normalized_data: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    resolution_action: str | None = None
    resolution_target_id: int | None = None
    resolution_target_unit_id: int | None = None
    resolution_target_owner_user_id: int | None = None
    resolution_target_vendor_id: int | None = None
    resolution_target_tenant_user_id: int | None = None
    resolution_target_gl_account_id: int | None = None
    resolved_by_platform_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class AppFolioStagedRowResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_property_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_property_id is None:
            raise ValueError("target_property_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_property_id is not None:
            raise ValueError("target_property_id is only valid for MATCH_EXISTING")
        return self


class AppFolioStagedPropertyCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppFolioUnitPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)


class AppFolioUnitDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioUnitPreviewRow]


class AppFolioStagedUnitResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_unit_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_unit_id is None:
            raise ValueError("target_unit_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_unit_id is not None:
            raise ValueError("target_unit_id is only valid for MATCH_EXISTING")
        return self


class AppFolioStagedOwnerResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_owner_user_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_owner_user_id is None:
            raise ValueError("target_owner_user_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_owner_user_id is not None:
            raise ValueError("target_owner_user_id is only valid for MATCH_EXISTING")
        return self


class AppFolioStagedTenantResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_tenant_user_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_tenant_user_id is None:
            raise ValueError("target_tenant_user_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_tenant_user_id is not None:
            raise ValueError("target_tenant_user_id is only valid for MATCH_EXISTING")
        return self


class AppFolioStagedLeaseOccupancyResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(ACCEPT_RELATIONSHIP|SKIP)$")


class AppFolioStagedGLAccountResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_gl_account_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_gl_account_id is None:
            raise ValueError("target_gl_account_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_gl_account_id is not None:
            raise ValueError("target_gl_account_id is only valid for MATCH_EXISTING")
        return self


class AppFolioStagedGeneralLedgerResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(ACCEPT_RELATIONSHIP|SKIP)$")


class AppFolioStagedBillResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(ACCEPT_RELATIONSHIP|SKIP)$")


class AppFolioStagedVendorResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_vendor_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_vendor_id is None:
            raise ValueError("target_vendor_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_vendor_id is not None:
            raise ValueError("target_vendor_id is only valid for MATCH_EXISTING")
        return self


class AppFolioStagedUnitCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppFolioUnitCommitRow(BaseModel):
    source_id: str
    target_unit_id: int
    replayed: bool


class AppFolioUnitCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int = 0
    warning_count: int
    rows: list[AppFolioUnitCommitRow]


class AppFolioOwnerPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)


class AppFolioOwnerDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioOwnerPreviewRow]


class AppFolioStagedOwnerCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppFolioOwnerCommitRow(BaseModel):
    source_id: str
    target_owner_user_id: int
    replayed: bool


class AppFolioOwnerCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    mapped_existing: int
    warning_count: int
    rows: list[AppFolioOwnerCommitRow]


class AppFolioTenantPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)


class AppFolioTenantDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioTenantPreviewRow]


class AppFolioStagedTenantCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppFolioTenantCommitRow(BaseModel):
    source_id: str
    target_tenant_user_id: int
    replayed: bool


class AppFolioTenantCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    mapped_existing: int
    warning_count: int
    rows: list[AppFolioTenantCommitRow]


class AppFolioGLAccountPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)


class AppFolioGLAccountDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioGLAccountPreviewRow]


class AppFolioStagedGLAccountCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppFolioGLAccountCommitRow(BaseModel):
    source_id: str
    target_gl_account_id: int
    replayed: bool


class AppFolioGLAccountCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    mapped_existing: int
    warning_count: int
    rows: list[AppFolioGLAccountCommitRow]


class AppFolioGeneralLedgerPreviewRow(BaseModel):
    source_id: str
    importable: bool = True
    reason: str | None = None
    source_evidence: dict[str, Any]
    resolved_targets: dict[str, int | None]
    warnings: list[str] = Field(default_factory=list)


class AppFolioGeneralLedgerDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioGeneralLedgerPreviewRow]


class AppFolioBillPreviewRow(BaseModel):
    source_id: str
    importable: bool = True
    reason: str | None = None
    source_evidence: dict[str, Any]
    resolved_targets: dict[str, int | None]
    warnings: list[str] = Field(default_factory=list)


class AppFolioBillDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioBillPreviewRow]


class AppFolioGeneralLedgerReadinessLine(BaseModel):
    source_id: str
    transaction_id: str
    posted_date: str
    debit: str
    credit: str
    resolved_targets: dict[str, int | None]


class AppFolioGeneralLedgerReadinessGroup(BaseModel):
    transaction_id: str
    line_count: int
    debit_total: str
    credit_total: str
    balanced: bool
    lines: list[AppFolioGeneralLedgerReadinessLine]


class AppFolioGeneralLedgerCommitReadinessOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    dry_run_fingerprint: str
    readiness_fingerprint: str
    replayed: bool
    group_count: int
    line_count: int
    groups: list[AppFolioGeneralLedgerReadinessGroup]


class AppFolioVendorPreviewRow(BaseModel):
    source_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)


class AppFolioVendorDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    invalid: int
    warning_count: int
    rows: list[AppFolioVendorPreviewRow]


class AppFolioStagedVendorCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class AppFolioVendorCommitRow(BaseModel):
    source_id: str
    target_vendor_id: int
    replayed: bool


class AppFolioVendorCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int = 0
    warning_count: int
    rows: list[AppFolioVendorCommitRow]
