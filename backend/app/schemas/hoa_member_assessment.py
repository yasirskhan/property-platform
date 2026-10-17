"""Explicit board assessment, verified responsible member, central GL posting."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HOAAssessmentBoardDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str = Field(min_length=3, max_length=1500)
    contact_link_id: int | None = Field(default=None, ge=1)
    member_user_id: int | None = Field(default=None, ge=1)
    offline_meeting_on: date | None = None
    decision_maker_seat_id: int | None = Field(default=None, ge=1)
    supporting_attachment_id: int | None = Field(default=None, ge=1)

    @field_validator("decision_note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A recorded board decision note is required.")
        return value.strip()

    @model_validator(mode="after")
    def coherent(self):
        if self.decision == "APPROVED" and (self.member_user_id is None or self.contact_link_id is None):
            raise ValueError("Approval requires the explicit responsible member and contact.")
        if self.decision == "DENIED" and (self.member_user_id is not None or self.contact_link_id is not None):
            raise ValueError("Denial must not designate a liable member.")
        if self.offline_meeting_on is not None and (not self.decision_maker_seat_id or not self.supporting_attachment_id):
            raise ValueError("Offline decision requires a board decision-maker and private record.")
        if self.offline_meeting_on is None and (self.decision_maker_seat_id is not None or self.supporting_attachment_id is not None):
            raise ValueError("Direct decisions do not accept offline-only fields.")
        return self


class HOAAssessmentBoardDecisionOut(BaseModel):
    id: int
    proposal_id: int
    property_id: int
    decision: Literal["APPROVED", "DENIED"]
    board_seat_id: int
    decision_maker_seat_id: int
    record_method: Literal["DIRECT", "OFFLINE"]
    decided_on: date
    contact_link_id: int | None
    member_user_id: int | None
    approved_amount: Decimal | None
    proposal_revision_at: datetime
    issued: bool = False


class HOAChargeIssueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    member_user_id: int = Field(ge=1)
    due_on: date
    receivable_gl_account_id: int = Field(ge=1)
    income_gl_account_id: int = Field(ge=1)


class HOAChargeReverseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    reversal_on: date
    reason: str = Field(min_length=3, max_length=500)


class HOAMemberChargeOut(BaseModel):
    id: int
    proposal_id: int
    occurrence_id: int
    property_id: int
    member_user_id: int
    amount: Decimal
    amount_paid: Decimal
    due_on: date
    status: Literal["OPEN", "PAID", "REVERSED"]
    gl_transaction_id: int
    reversal_transaction_id: int | None
    issued_at: datetime
    member_receivable: Literal[True] = True
    tenant_charge_inferred: Literal[False] = False
