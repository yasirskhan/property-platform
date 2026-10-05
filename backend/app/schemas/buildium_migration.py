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


class BuildiumUnitResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|CREATE_NEW|SKIP)$")
    target_unit_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_unit_id is None:
            raise ValueError("target_unit_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_unit_id is not None:
            raise ValueError("target_unit_id is only valid for MATCH_EXISTING")
        return self


class BuildiumUnitDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumUnitResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumUnitPreviewRow(BaseModel):
    source_id: str | None
    source_property_id: str | None
    importable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_unit_id: int | None = None


class BuildiumUnitDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    importable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumUnitPreviewRow]


class BuildiumUnitCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumUnitResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumUnitCommitRow(BaseModel):
    source_id: str
    target_unit_id: int
    replayed: bool


class BuildiumUnitCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    committed: int
    matched_existing: int = 0
    skipped_review: int = 0
    warning_count: int
    rows: list[BuildiumUnitCommitRow]


class BuildiumOwnerResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_owner_user_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_owner_user_id is None:
            raise ValueError("target_owner_user_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_owner_user_id is not None:
            raise ValueError("target_owner_user_id is only valid for MATCH_EXISTING")
        return self


class BuildiumOwnerDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumOwnerResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumOwnerPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_owner_user_id: int | None = None


class BuildiumOwnerDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_inactive: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumOwnerPreviewRow]


class BuildiumOwnerCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumOwnerResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumOwnerCommitRow(BaseModel):
    source_id: str
    target_owner_user_id: int
    replayed: bool


class BuildiumOwnerCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_inactive: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumOwnerCommitRow]


class BuildiumVendorResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_vendor_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_vendor_id is None:
            raise ValueError("target_vendor_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_vendor_id is not None:
            raise ValueError("target_vendor_id is only valid for MATCH_EXISTING")
        return self


class BuildiumVendorDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumVendorResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumVendorPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_vendor_id: int | None = None


class BuildiumVendorDryRunOut(BaseModel):
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
    rows: list[BuildiumVendorPreviewRow]


class BuildiumVendorCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumVendorResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumVendorCommitRow(BaseModel):
    source_id: str
    target_vendor_id: int
    replayed: bool


class BuildiumVendorCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumVendorCommitRow]


class BuildiumTenantResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_tenant_user_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_tenant_user_id is None:
            raise ValueError("target_tenant_user_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_tenant_user_id is not None:
            raise ValueError("target_tenant_user_id is only valid for MATCH_EXISTING")
        return self


class BuildiumTenantDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumTenantResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumTenantPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_tenant_user_id: int | None = None


class BuildiumTenantDryRunOut(BaseModel):
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
    rows: list[BuildiumTenantPreviewRow]


class BuildiumTenantCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumTenantResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumTenantCommitRow(BaseModel):
    source_id: str
    target_tenant_user_id: int
    replayed: bool


class BuildiumTenantCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumTenantCommitRow]

class BuildiumLeaseResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_lease_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_lease_id is None:
            raise ValueError("target_lease_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_lease_id is not None:
            raise ValueError("target_lease_id is only valid for MATCH_EXISTING")
        return self


class BuildiumLeaseDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumLeaseResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumLeasePreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_lease_id: int | None = None


class BuildiumLeaseDryRunOut(BaseModel):
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
    rows: list[BuildiumLeasePreviewRow]


class BuildiumLeaseCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumLeaseResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumLeaseCommitRow(BaseModel):
    source_id: str
    target_lease_id: int
    replayed: bool


class BuildiumLeaseCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumLeaseCommitRow]

class BuildiumGLAccountResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_gl_account_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_gl_account_id is None:
            raise ValueError("target_gl_account_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_gl_account_id is not None:
            raise ValueError("target_gl_account_id is only valid for MATCH_EXISTING")
        return self


class BuildiumGLAccountDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    resolutions: list[BuildiumGLAccountResolutionIn] = Field(default_factory=list, max_length=1000)


class BuildiumGLAccountPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_gl_account_id: int | None = None


class BuildiumGLAccountDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_inactive: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumGLAccountPreviewRow]


class BuildiumGLAccountCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    include_inactive: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    resolutions: list[BuildiumGLAccountResolutionIn] = Field(default_factory=list, max_length=1000)


class BuildiumGLAccountCommitRow(BaseModel):
    source_id: str
    target_gl_account_id: int
    replayed: bool


class BuildiumGLAccountCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_inactive: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumGLAccountCommitRow]



class BuildiumWorkOrderResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_work_order_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_work_order_id is None:
            raise ValueError("target_work_order_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_work_order_id is not None:
            raise ValueError("target_work_order_id is only valid for MATCH_EXISTING")
        return self


class BuildiumWorkOrderDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumWorkOrderResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumWorkOrderPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_work_order_id: int | None = None


class BuildiumWorkOrderDryRunOut(BaseModel):
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
    rows: list[BuildiumWorkOrderPreviewRow]


class BuildiumWorkOrderCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumWorkOrderResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumWorkOrderCommitRow(BaseModel):
    source_id: str
    target_work_order_id: int
    replayed: bool


class BuildiumWorkOrderCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumWorkOrderCommitRow]



class BuildiumBillResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_bill_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_bill_id is None:
            raise ValueError("target_bill_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_bill_id is not None:
            raise ValueError("target_bill_id is only valid for MATCH_EXISTING")
        return self


class BuildiumBillDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBillResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumBillPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_bill_id: int | None = None


class BuildiumBillDryRunOut(BaseModel):
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
    rows: list[BuildiumBillPreviewRow]


class BuildiumBillCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBillResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumBillCommitRow(BaseModel):
    source_id: str
    target_bill_id: int
    replayed: bool


class BuildiumBillCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumBillCommitRow]



class BuildiumBankAccountResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_bank_account_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_bank_account_id is None:
            raise ValueError("target_bank_account_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_bank_account_id is not None:
            raise ValueError("target_bank_account_id is only valid for MATCH_EXISTING")
        return self


class BuildiumBankAccountDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBankAccountResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumBankAccountPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_bank_account_id: int | None = None


class BuildiumBankAccountDryRunOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_inactive: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[BuildiumBankAccountPreviewRow]


class BuildiumBankAccountCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    include_inactive: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBankAccountResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumBankAccountCommitRow(BaseModel):
    source_id: str
    target_bank_account_id: int
    replayed: bool


class BuildiumBankAccountCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_inactive: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumBankAccountCommitRow]



class BuildiumBillPaymentResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_check_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_check_id is None:
            raise ValueError("target_check_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_check_id is not None:
            raise ValueError("target_check_id is only valid for MATCH_EXISTING")
        return self


class BuildiumBillPaymentDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBillPaymentResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumBillPaymentPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_check_id: int | None = None


class BuildiumBillPaymentDryRunOut(BaseModel):
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
    rows: list[BuildiumBillPaymentPreviewRow]


class BuildiumBillPaymentCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumBillPaymentResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumBillPaymentCommitRow(BaseModel):
    source_id: str
    target_check_id: int
    replayed: bool


class BuildiumBillPaymentCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumBillPaymentCommitRow]



class BuildiumOwnerPropertyResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_owner_id: int = Field(ge=1)
    source_property_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_property_owner_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_property_owner_id is None:
            raise ValueError("target_property_owner_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_property_owner_id is not None:
            raise ValueError("target_property_owner_id is only valid for MATCH_EXISTING")
        return self


class BuildiumOwnerPropertyDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumOwnerPropertyResolutionIn] = Field(default_factory=list, max_length=1000)


class BuildiumOwnerPropertyPreviewRow(BaseModel):
    source_owner_id: str | None
    source_property_id: str | None
    source_relationship: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_property_owner_id: int | None = None


class BuildiumOwnerPropertyDryRunOut(BaseModel):
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
    rows: list[BuildiumOwnerPropertyPreviewRow]


class BuildiumOwnerPropertyCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumOwnerPropertyResolutionIn] = Field(default_factory=list, max_length=1000)


class BuildiumOwnerPropertyCommitRow(BaseModel):
    source_relationship: str
    target_property_owner_id: int
    replayed: bool


class BuildiumOwnerPropertyCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumOwnerPropertyCommitRow]


class BuildiumPropertyGroupResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(ge=1)
    action: str = Field(pattern=r"^(MATCH_EXISTING|SKIP)$")
    target_property_group_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self):
        if self.action == "MATCH_EXISTING" and self.target_property_group_id is None:
            raise ValueError("target_property_group_id is required for MATCH_EXISTING")
        if self.action != "MATCH_EXISTING" and self.target_property_group_id is not None:
            raise ValueError("target_property_group_id is only valid for MATCH_EXISTING")
        return self


class BuildiumPropertyGroupDryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumPropertyGroupResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumPropertyGroupPreviewRow(BaseModel):
    source_id: str | None
    reviewable: bool
    reason: str | None
    mapped: dict[str, Any] | None
    warnings: list[str] = Field(default_factory=list)
    resolution_action: str | None = None
    resolution_target_property_group_id: int | None = None


class BuildiumPropertyGroupDryRunOut(BaseModel):
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
    rows: list[BuildiumPropertyGroupPreviewRow]


class BuildiumPropertyGroupCommitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    resolutions: list[BuildiumPropertyGroupResolutionIn] = Field(default_factory=list, max_length=500)


class BuildiumPropertyGroupCommitRow(BaseModel):
    source_id: str
    target_property_group_id: int
    replayed: bool


class BuildiumPropertyGroupCommitOut(BaseModel):
    run_id: int
    organization_id: int
    provider: str
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[BuildiumPropertyGroupCommitRow]
