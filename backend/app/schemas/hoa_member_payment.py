"""Manually recorded HOA member payments; receipt and central GL backed."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAMemberPaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    member_user_id: int = Field(ge=1)
    cash_gl_account_id: int = Field(ge=1)
    received_on: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_reference: str = Field(min_length=3, max_length=60)
    idempotency_key: str = Field(min_length=12, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    @field_validator("payment_reference")
    @classmethod
    def trim_reference(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A recorded payment reference is required.")
        return value.strip()


class HOAMemberPaymentReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    reversal_on: date
    reason: str = Field(min_length=3, max_length=600)
    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Payment reversal reason is required.")
        return value.strip()


class HOAMemberPaymentOut(BaseModel):
    id: int
    charge_id: int
    property_id: int
    member_user_id: int
    amount: Decimal
    received_on: date
    payment_reference: str
    cash_gl_account_id: int
    receipt_id: int
    status: Literal["POSTED", "REVERSED"]
    reversal_receipt_id: int | None
    reversed_on: date | None
    created_at: datetime
    manually_recorded: Literal[True] = True
    bank_collection_executed: Literal[False] = False


class HOAReceiptCashOption(BaseModel):
    id: int
    number: str
    name: str
