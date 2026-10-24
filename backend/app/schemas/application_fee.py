"""Fee preparation never accepts a price, org, payer or payment status."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApplicationFeePrepareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9:_-]+$")


class ApplicationFeePrepareOut(BaseModel):
    application_id: int
    attempt_id: int
    amount_cents: int
    currency: Literal["USD"]
    status: Literal["PREPARED"]
    checkout_available: bool = False
    created_at: datetime


class ApplicationFeeRecordReceiptIn(BaseModel):
    """Requires explicit staff verification of an existing posted receipt."""
    model_config = ConfigDict(extra="forbid")
    receipt_id: int = Field(ge=1)
    attested_received_and_matched: Literal[True]
