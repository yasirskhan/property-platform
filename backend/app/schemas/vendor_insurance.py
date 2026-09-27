"""Recorded vendor policy metadata; status is relative to a reference date."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VendorInsuranceCreate(BaseModel):
    carrier: str = Field(min_length=1, max_length=255)
    coverage_type: str = Field(min_length=1, max_length=100)
    policy_number: str | None = Field(default=None, max_length=100)
    coverage_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    effective_date: date | None = None
    expiration_date: date

    @field_validator("carrier", "coverage_type")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Vendor insurance provider and coverage are required")
        return value

    @model_validator(mode="after")
    def dates_consistent(self):
        if self.effective_date and self.effective_date > self.expiration_date:
            raise ValueError("Effective date cannot exceed expiration date")
        return self


class VendorInsuranceUpdate(BaseModel):
    carrier: str | None = Field(default=None, max_length=255)
    coverage_type: str | None = Field(default=None, max_length=100)
    policy_number: str | None = Field(default=None, max_length=100)
    coverage_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    effective_date: date | None = None
    expiration_date: date | None = None

    @field_validator("carrier", "coverage_type")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Vendor insurance provider and coverage are required")
        return value


class VendorInsuranceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    carrier: str
    coverage_type: str
    policy_number: str | None
    coverage_amount: Decimal | None
    effective_date: date | None
    expiration_date: date
    is_active: bool
    status: Literal["INACTIVE", "UPCOMING", "EXPIRED", "EXPIRING_30_DAYS", "CURRENT"]
    created_at: datetime
    updated_at: datetime


class VendorInsuranceListOut(BaseModel):
    items: list[VendorInsuranceOut]
    total: int
    as_of: date
