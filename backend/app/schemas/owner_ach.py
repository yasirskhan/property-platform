from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class OwnerACHUpsertIn(BaseModel):
    account_holder_name: str = Field(..., min_length=1, max_length=120)
    bank_name: Optional[str] = Field(None, max_length=200)
    routing_number: str = Field(..., min_length=9, max_length=9)
    account_number: str = Field(..., min_length=1, max_length=40)
    account_type: Literal["CHECKING", "SAVINGS"] = "CHECKING"
    is_enabled: bool = True

    @field_validator("routing_number")
    @classmethod
    def routing_digits(cls, value: str) -> str:
        value = value.strip()
        if len(value) != 9 or not value.isdigit():
            raise ValueError("routing_number must contain exactly 9 digits")
        return value

    @field_validator("account_number")
    @classmethod
    def account_chars(cls, value: str) -> str:
        value = value.strip().replace(" ", "").replace("-", "")
        if not value or len(value) > 40 or not value.isalnum():
            raise ValueError("account_number contains unsupported characters")
        return value


class OwnerACHOut(BaseModel):
    owner_id: int
    configured: bool
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    routing_last4: Optional[str] = None
    account_last4: Optional[str] = None
    account_type: Optional[Literal["CHECKING", "SAVINGS"]] = None
    is_enabled: bool = False
    updated_at: Optional[datetime] = None
