"""HOA reserve book mapping, not legal reserve ownership or bank clearing."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOAReserveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    gl_account_id: int = Field(ge=1)
    bank_account_id: int | None = Field(default=None, ge=1)


class HOAReserveOut(BaseModel):
    id: int
    association_id: int
    property_id: int
    gl_account_id: int
    gl_number: str
    gl_name: str
    bank_account_id: int | None
    bank_display_name: str | None
    mapping_status: str
    status: Literal["STAFF_MAPPED_UNVERIFIED"] = "STAFF_MAPPED_UNVERIFIED"
    posting_enabled: Literal[False] = False


class HOAReserveBookOut(HOAReserveOut):
    as_of: date
    account_wide_book_balance: Decimal
    property_tagged_book_balance: Decimal
    unallocated_or_other_property_balance: Decimal
    attribution_status: str
    bank_statement_reconciled: Literal[False] = False
    legal_reserve_ownership_verified: Literal[False] = False


class HOAReserveOptionOut(BaseModel):
    gl_account_id: int
    gl_number: str
    gl_name: str
    bank_account_id: int | None
    bank_display_name: str | None
