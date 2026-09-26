"""Tax profile input never serializes its TIN into output, audit, or errors."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class TaxProfileUpsertIn(BaseModel):
    subject_type: Literal["ORGANIZATION", "OWNER", "VENDOR"]
    subject_id: int = Field(ge=1)
    legal_name: str = Field(min_length=1, max_length=200)
    business_name: str | None = Field(default=None, max_length=200)
    tax_classification: Literal[
        "INDIVIDUAL", "SOLE_PROPRIETOR", "C_CORP", "S_CORP", "PARTNERSHIP",
        "TRUST_ESTATE", "LLC", "OTHER",
    ]
    tin_type: Literal["SSN", "EIN", "ITIN"]
    tin: SecretStr = Field(repr=False)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=50)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="USA", min_length=1, max_length=100)
    # Paper W-9 confirmation only. No electronic substitute-W-9 claim.
    w9_on_file: bool = False
    w9_received_on: date | None = None

    @field_validator("legal_name", "address_line1", "city", "state", "postal_code", "country")
    @classmethod
    def required_text(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Required tax profile field cannot be blank")
        return clean

    @model_validator(mode="after")
    def paper_w9_consistency(self):
        if self.subject_type == "ORGANIZATION":
            if self.w9_on_file or self.w9_received_on:
                raise ValueError("Payer does not have a recipient W-9 status")
        elif self.w9_on_file != (self.w9_received_on is not None):
            raise ValueError("Paper W-9 confirmation and received date must be supplied together")
        return self


class TaxProfileOut(BaseModel):
    id: int
    subject_type: str
    subject_id: int
    tin_last4: str
    w9_on_file: bool
    w9_received_on: date | None
    updated_at: datetime
