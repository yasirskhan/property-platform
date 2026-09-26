from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BankFeedImportIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=5_000_000)


class BankFeedTransactionOut(BaseModel):
    id: int
    bank_account_id: int
    posted_date: date
    amount: Decimal
    payee: Optional[str] = None
    description: Optional[str] = None
    memo: Optional[str] = None
    reference_number: Optional[str] = None
    source_provider: str
    external_id: Optional[str] = None
    status: Literal["MATCHED", "UNMATCHED"]
    matched_source_type: Optional[str] = None
    matched_source_id: Optional[int] = None
    created_at: datetime


class BankFeedListOut(BaseModel):
    items: list[BankFeedTransactionOut]
    total: int


class BankFeedImportOut(BaseModel):
    imported: int
    duplicates: int
    matched: int
    total: int


class BankFeedRematchOut(BaseModel):
    matched: int
    remaining_unmatched: int
