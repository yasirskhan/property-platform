"""Prospective reserve movement is not a transfer, payment or GL posting."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOAReserveMovementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    counterparty_gl_account_id: int = Field(ge=1)
    direction: Literal["TO_RESERVE", "FROM_RESERVE"]
    planned_on: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    memo: str = Field(min_length=1, max_length=240)
    idempotency_key: str = Field(min_length=12, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class HOAReserveMovementOut(BaseModel):
    id: int
    property_id: int
    association_id: int
    reserve_gl_account_id: int
    counterparty_gl_account_id: int
    direction: Literal["TO_RESERVE", "FROM_RESERVE"]
    planned_on: date
    amount: Decimal
    memo: str
    status: Literal["DRAFT", "CANCELLED"]
    created_at: datetime
    cancelled_at: datetime | None
    posting_enabled: Literal[False] = False
    funds_moved: Literal[False] = False
    legally_restricted_funds_verified: Literal[False] = False
