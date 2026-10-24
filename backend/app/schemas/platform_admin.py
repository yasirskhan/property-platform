"""Schemas for the separate internal platform administration API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.release_gate import ReleaseStage


class PlatformOrganizationCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    data_region: str = Field(default="us-east-1", min_length=2, max_length=32)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter code")
        return normalized

    @field_validator("data_region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("data_region is required")
        return normalized


class PlatformOrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    state: str
    currency: str
    data_region: str
    is_active: bool
    subscription_status: str | None
    plan_id: int | None
    plan_name: str | None
    created_at: datetime | None


class PlatformPricingTierCreateIn(BaseModel):
    min_properties: int = Field(ge=1)
    max_properties: int | None = Field(default=None, ge=1)
    monthly_price_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter code")
        return normalized


class PlatformPricingTierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    min_properties: int
    max_properties: int | None
    monthly_price_cents: int
    currency: str


class PlatformPlanCreateIn(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    pricing_tiers: list[PlatformPricingTierCreateIn] = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class PlatformPlanUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class PlatformPlanOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    module_keys: list[str]
    pricing_tiers: list[PlatformPricingTierOut]
    created_at: datetime
    updated_at: datetime


class PlatformAuditOut(BaseModel):
    id: int
    platform_user_id: int
    platform_user_email: str | None
    organization_id: int | None
    entity_type: str
    entity_id: int
    action: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    ip_address: str | None
    created_at: datetime


class PlatformReleaseGateRead(BaseModel):
    key: str
    stage: ReleaseStage
    organization_ids: list[int]
    updated_at: datetime
