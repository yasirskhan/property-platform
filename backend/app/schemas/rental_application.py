"""Non-sensitive rental application draft API.

Never accept or serialize legacy plaintext applicant_ssn, DOB,
screening reports, fee/payout status or provider payment tokens.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class ApplicantDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    applicant_name: str = Field(min_length=1, max_length=255)
    applicant_email: EmailStr
    applicant_phone: str | None = Field(default=None, max_length=50)
    move_in_date: date | None = None
    lease_term_months: int | None = Field(default=None, ge=1, le=60)
    occupant_names: list[str] = Field(default_factory=list, max_length=8)
    pet_description: str | None = Field(default=None, max_length=500)

    @field_validator("applicant_name")
    @classmethod
    def name_nonblank(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Applicant name is required.")
        return name

    @field_validator("occupant_names")
    @classmethod
    def occupant_names_bounded(cls, values: list[str]) -> list[str]:
        cleaned = [name.strip() for name in values]
        if any(not name or len(name) > 150 for name in cleaned):
            raise ValueError("Occupant names must be nonempty and at most 150 characters.")
        return cleaned


class RentalApplicationCreate(ApplicantDetails):
    property_id: int = Field(ge=1)
    unit_id: int | None = Field(default=None, ge=1)


class RentalApplicationEdit(ApplicantDetails):
    pass


class RentalApplicationOut(BaseModel):
    id: int
    property_id: int
    unit_id: int | None
    applicant_user_id: int
    status: Literal[
        "draft", "pending_payment", "paid", "screening", "screened",
        "approved", "rejected", "withdrawn",
    ]
    applicant_name: str
    applicant_email: str
    applicant_phone: str | None
    move_in_date: date | None
    lease_term_months: int | None
    occupant_names: list[str]
    pet_description: str | None
    created_at: datetime
    updated_at: datetime
