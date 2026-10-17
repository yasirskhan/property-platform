from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class OwnerPayoutEntryIn(BaseModel):
    owner_id: int
    amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=14)


class OwnerPayoutDraftIn(BaseModel):
    bank_account_id: int
    effective_date: date
    payouts: list[OwnerPayoutEntryIn] = Field(..., min_length=1, max_length=500)


class OwnerPayoutConfirmIn(BaseModel):
    confirmation_date: date


class OwnerPayoutCandidateOut(BaseModel):
    owner_id: int
    owner_name: str
    owner_email: str
    available_balance: Decimal
    ach_configured: bool
    ach_enabled: bool
    account_last4: Optional[str] = None
    can_pay: bool
    reason: Optional[str] = None


class OwnerPayoutPreviewOut(BaseModel):
    bank_account_id: int
    bank_account_name: str
    book_balance: Decimal
    candidates: list[OwnerPayoutCandidateOut]


class OwnerPayoutOut(BaseModel):
    id: int
    batch_reference: str
    owner_id: int
    owner_name: str
    owner_email: str
    bank_account_id: int
    bank_account_name: str
    effective_date: date
    amount: Decimal
    destination_last4: str
    status: str
    gl_transaction_id: Optional[int] = None
    created_by_id: Optional[int] = None
    confirmed_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None


class OwnerPayoutDraftOut(BaseModel):
    batch_reference: str
    entry_count: int
    total_amount: Decimal
    funds_moved: bool = False
    accounting_posted: bool = False
    payouts: list[OwnerPayoutOut]


class OwnerPayoutConfirmOut(BaseModel):
    batch_reference: str
    entry_count: int
    total_amount: Decimal
    funds_moved_by_app: bool = False
    externally_confirmed: bool = True
    accounting_posted: bool = True
    payouts: list[OwnerPayoutOut]


class OwnerPayoutListOut(BaseModel):
    items: list[OwnerPayoutOut]
    total: int
