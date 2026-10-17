from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ACHEntryIn(BaseModel):
    recipient_name: str = Field(..., min_length=1, max_length=22)
    routing_number: str = Field(..., min_length=9, max_length=9)
    account_number: str = Field(..., min_length=1, max_length=17)
    account_type: Literal["CHECKING", "SAVINGS"] = "CHECKING"
    amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
    identification: Optional[str] = Field(None, max_length=15)

    @field_validator("routing_number")
    @classmethod
    def routing_digits(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) != 9:
            raise ValueError("routing_number must contain exactly 9 digits")
        return value

    @field_validator("account_number")
    @classmethod
    def account_chars(cls, value: str) -> str:
        value = value.strip().replace(" ", "")
        if not value or not value.replace("-", "").isalnum():
            raise ValueError("account_number contains unsupported characters")
        return value


class ACHGenerateIn(BaseModel):
    effective_date: date
    company_id: Optional[str] = Field(None, max_length=10)
    entry_description: str = Field("PAYMENT", min_length=1, max_length=10)
    entries: list[ACHEntryIn] = Field(..., min_length=1, max_length=500)


class ACHGenerateOut(BaseModel):
    format: Literal["CSV", "NACHA"]
    filename: str
    content_type: str
    content: str
    entry_count: int
    total_amount: Decimal


class ACHTestFileIn(BaseModel):
    effective_date: date
    company_id: Optional[str] = Field(None, max_length=10)
    entry_description: str = Field("PRENOTE", min_length=1, max_length=10)


class ACHTestFileOut(BaseModel):
    format: Literal["CSV", "NACHA"]
    filename: str
    content_type: str
    content: str
    owner_id: int
    amount: Decimal = Decimal("0.00")
