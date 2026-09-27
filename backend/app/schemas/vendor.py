"""Vendor company API: no taxpayer identifiers or inferred payable links."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class VendorFields(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    trade: str | None = Field(default=None, max_length=100)
    business_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    contact_user_id: int | None = Field(default=None, ge=1)

    @field_validator("company_name")
    @classmethod
    def require_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Vendor company name is required")
        return clean


class VendorCreate(VendorFields):
    pass


class VendorUpdate(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    trade: str | None = Field(default=None, max_length=100)
    business_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    contact_user_id: int | None = Field(default=None, ge=1)

    @field_validator("company_name")
    @classmethod
    def nonblank_if_supplied(cls, value: str | None) -> str | None:
        if value is None:
            return value
        clean = value.strip()
        if not clean:
            raise ValueError("Vendor company name is required")
        return clean


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    company_name: str
    trade: str | None
    business_email: EmailStr | None
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    contact_user_id: int | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VendorListOut(BaseModel):
    items: list[VendorOut]
    total: int
