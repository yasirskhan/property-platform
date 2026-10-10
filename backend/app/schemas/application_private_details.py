"""Address/income questionnaire: no SSN/DOB/bank/payment/screening fields."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AddressIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=50)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="USA", min_length=1, max_length=100)

    @field_validator("address_line1", "city", "state", "postal_code", "country")
    @classmethod
    def required_nonblank(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Address fields cannot be blank.")
        return clean


class PrivateApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_address: AddressIn
    previous_addresses: list[AddressIn] = Field(default_factory=list, max_length=3)
    employer_name: str | None = Field(default=None, max_length=200)
    employment_title: str | None = Field(default=None, max_length=100)
    gross_monthly_income: Decimal | None = Field(default=None, gt=0, le=10000000, max_digits=12, decimal_places=2)


class PrivateApplicationOut(BaseModel):
    application_id: int
    configured: bool
    details: PrivateApplicationIn | None = None
    updated_at: datetime | None = None
