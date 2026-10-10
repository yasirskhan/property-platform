"""Recorded board authority and posted reserve book transfers."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class HOAReserveDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str = Field(min_length=3, max_length=1500)
    offline_meeting_on: date | None = None
    maker_seat_id: int | None = Field(default=None, ge=1)
    supporting_attachment_id: int | None = Field(default=None, ge=1)
    @field_validator("decision_note")
    @classmethod
    def trim_note(cls, text: str) -> str:
        if not text.strip():
            raise ValueError("Board decision note is required.")
        return text.strip()
    @model_validator(mode="after")
    def coherent(self):
        if self.offline_meeting_on is None and (self.maker_seat_id or self.supporting_attachment_id):
            raise ValueError("Offline-only board fields require an offline date.")
        if self.offline_meeting_on is not None and (not self.maker_seat_id or not self.supporting_attachment_id):
            raise ValueError("Offline decision requires decision-maker and private record.")
        return self

class HOAReservePostIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    transaction_on: date

class HOAReserveReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    reversal_on: date
    reason: str = Field(min_length=3, max_length=600)
    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reversal reason is required.")
        return value.strip()

class HOAReserveDecisionOut(BaseModel):
    id: int
    draft_id: int
    property_id: int
    decision: Literal["APPROVED", "DENIED"]
    status: Literal["APPROVED", "DENIED", "POSTED", "REVERSED"]
    board_seat_id: int
    maker_seat_id: int
    record_method: Literal["DIRECT", "OFFLINE"]
    decided_on: date
    amount: Decimal | None
    direction: Literal["TO_RESERVE", "FROM_RESERVE"]
    reserve_gl_account_id: int
    counterparty_gl_account_id: int
    gl_transaction_id: int | None
    reversal_transaction_id: int | None
    posted_on: date | None
    reversed_on: date | None
    bank_transfer_executed: Literal[False] = False
