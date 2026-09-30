"""Explicit HOA fine board outcome and separately authorized receivable posting."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HOAFineDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    decision: Literal["APPROVED", "DENIED"]
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    member_user_id: int | None = Field(default=None, ge=1)
    decision_note: str = Field(min_length=3, max_length=1500)
    hearing_record_id: int | None = Field(default=None, ge=1)
    hearing_disposition: Literal["NO_REQUEST_RECORDED", "HEARING_HELD"] | None = None
    hearing_held_on: date | None = None
    hearing_record_attachment_id: int | None = Field(default=None, ge=1)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("decision_note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        result = value.strip()
        if len(result) < 3:
            raise ValueError("A substantive decision note is required.")
        return result

    @model_validator(mode="after")
    def coherent(self):
        if self.decision == "APPROVED" and (self.amount is None or self.member_user_id is None):
            raise ValueError("Approval needs exact fine amount and verified liable member.")
        if self.decision == "DENIED" and (self.amount is not None or self.member_user_id is not None):
            raise ValueError("Denied fine must not create member liability.")
        if self.hearing_disposition == "HEARING_HELD" and (self.hearing_record_attachment_id is None or self.hearing_held_on is None):
            raise ValueError("Held hearing snapshot requires its actual date and private case-linked record.")
        if self.hearing_disposition == "NO_REQUEST_RECORDED" and (self.hearing_record_attachment_id is not None or self.hearing_held_on is not None):
            raise ValueError("No-request snapshot cannot contain a held hearing date or record.")
        if self.hearing_disposition is None and (self.hearing_record_attachment_id is not None or self.hearing_held_on is not None):
            raise ValueError("Hearing snapshot fields require a disposition.")
        return self


class HOAHearingRecordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    disposition: Literal["NO_REQUEST_RECORDED", "HEARING_HELD"]
    held_on: date | None = None
    record_attachment_id: int | None = Field(default=None, ge=1)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def coherent(self):
        if self.disposition == "HEARING_HELD" and (self.held_on is None or self.record_attachment_id is None):
            raise ValueError("Held hearing requires actual date and private case evidence.")
        if self.disposition == "NO_REQUEST_RECORDED" and (self.held_on is not None or self.record_attachment_id is not None):
            raise ValueError("No-request hearing record cannot include a held date or proof.")
        return self


class HOAHearingRecordOut(BaseModel):
    id: int
    case_id: int
    service_record_id: int
    policy_revision: int
    member_user_id: int
    disposition: Literal["NO_REQUEST_RECORDED", "HEARING_HELD"]
    held_on: date | None
    record_attachment_id: int | None
    board_seat_id: int
    recorded_at: datetime
    platform_certifies_hearing: Literal[False] = False


class HOAFinePostIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    posting_on: date
    receivable_gl_account_id: int = Field(ge=1)
    income_gl_account_id: int = Field(ge=1)


class HOAFineReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    reversal_on: date
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        result = value.strip()
        if len(result) < 3:
            raise ValueError("A substantive reversal reason is required.")
        return result


class HOAFineOut(BaseModel):
    id: int
    case_id: int
    property_id: int
    decision: Literal["APPROVED", "DENIED"]
    status: Literal["APPROVED", "DENIED", "POSTED", "REVERSED"]
    member_user_id: int | None
    amount: Decimal | None
    amount_paid: Decimal
    hearing_record_id: int | None
    hearing_disposition: str
    hearing_held_on: date | None
    hearing_record_attachment_id: int | None
    board_seat_id: int
    service_record_id: int
    policy_revision: int
    decided_on: date
    receivable_gl_account_id: int | None
    income_gl_account_id: int | None
    gl_transaction_id: int | None
    reversal_transaction_id: int | None
    posted_on: date | None
    reversed_on: date | None
    decision_note: str
    recorded_at: datetime
    direct_board_decision: Literal[True] = True
    tenant_charge_inferred: Literal[False] = False
