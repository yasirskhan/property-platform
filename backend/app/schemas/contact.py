"""Contact address-book payloads never create a user identity or hold TIN data."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ContactFields(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    contact_type: Literal["PERSON", "BUSINESS"] = "PERSON"
    company_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=100)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)

    @field_validator("display_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Contact name cannot be blank")
        return name


class ContactCreate(ContactFields):
    pass


class ContactUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    contact_type: Literal["PERSON", "BUSINESS"] | None = None
    company_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=100)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)

    @field_validator("display_name")
    @classmethod
    def nonblank_if_supplied(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("Contact name cannot be blank")
        return name


class ContactOut(ContactFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactListOut(BaseModel):
    items: list[ContactOut]
    total: int
