"""HOA ARC review states and recorded board decision contracts."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ARCStatus = Literal["SUBMITTED", "UNDER_REVIEW", "MORE_INFO_REQUESTED", "INFO_RECEIVED", "READY_FOR_DECISION", "DECISION_PREPARED", "APPROVED", "DENIED"]
ARCEventType = Literal["START_REVIEW", "REQUEST_MORE_INFO", "RECORD_INFO_RECEIVED", "MARK_READY_FOR_DECISION", "PREPARE_APPROVAL", "PREPARE_DENIAL"]


class HOAARCApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    intake_id: int = Field(ge=1)
    applicant_contact_link_id: int = Field(ge=1)
    submitted_on: date


class HOAARCDecisionFeeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    due_on: date
    receivable_gl_account_id: int = Field(ge=1)
    income_gl_account_id: int = Field(ge=1)


class HOAARCDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str = Field(min_length=1, max_length=1500)
    fee: HOAARCDecisionFeeIn | None = None
    follow_up_unit_id: int | None = Field(default=None, ge=1)
    follow_up_description: str | None = Field(default=None, min_length=10, max_length=1000)

    @field_validator("decision_note")
    @classmethod
    def nonempty_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Board decision note required")
        return value.strip()


class HOAARCDecisionOut(BaseModel):
    id: int
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str
    board_seat_id: int
    decided_at: datetime
    member_charge_id: int | None = None
    member_charge_amount: Decimal | None = None
    member_charge_due_on: date | None = None
    fee_gl_transaction_id: int | None = None
    work_order_id: int | None = None
    notification_status: str


class HOAARCApplicationOut(BaseModel):
    id: int
    association_id: int
    property_id: int
    intake_id: int
    applicant_contact_link_id: int
    applicant_contact_name: str
    submitted_on: date
    status: ARCStatus
    decision_preparation: Literal["APPROVE", "DENY"] | None = None
    board_decision: HOAARCDecisionOut | None = None
    updated_at: datetime


class HOAARCReviewEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: ARCEventType
    staff_note: str | None = Field(default=None, max_length=1500)

    @field_validator("staff_note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class HOAARCReviewEventOut(BaseModel):
    id: int
    event_type: ARCEventType | Literal["APPLICATION_SUBMITTED", "BOARD_APPROVED", "BOARD_DENIED"]
    staff_note: str | None
    created_at: datetime


class HOAARCAttachmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attachment_id: int = Field(ge=1)


class HOAARCAttachmentOut(BaseModel):
    id: int
    attachment_id: int
    filename: str
    recorded_at: datetime
    private_only: Literal[True] = True


class HOAARCApplicationDetailOut(HOAARCApplicationOut):
    events: list[HOAARCReviewEventOut]
    attachments: list[HOAARCAttachmentOut]
