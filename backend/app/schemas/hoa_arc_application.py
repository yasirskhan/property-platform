"""HOA ARC application review and board-recorded decisions."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ARCStatus = Literal[
    "SUBMITTED", "UNDER_REVIEW", "MORE_INFO_REQUESTED",
    "INFO_RECEIVED", "READY_FOR_DECISION", "DECISION_PREPARED",
    "APPROVED", "DENIED",
]
ARCEventType = Literal[
    "START_REVIEW", "REQUEST_MORE_INFO", "RECORD_INFO_RECEIVED",
    "MARK_READY_FOR_DECISION", "PREPARE_APPROVAL", "PREPARE_DENIAL",
]


class HOAARCApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    intake_id: int = Field(ge=1)
    applicant_contact_link_id: int = Field(ge=1)
    submitted_on: date


class HOAARCDecisionFeeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_user_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    due_on: date
    receivable_gl_account_id: int = Field(ge=1)
    income_gl_account_id: int = Field(ge=1)


class HOAARCDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str = Field(min_length=1, max_length=1500)
    offline_meeting_on: date | None = None
    decision_maker_seat_id: int | None = Field(default=None, ge=1)
    supporting_attachment_id: int | None = Field(default=None, ge=1)
    fee: HOAARCDecisionFeeIn | None = None
    follow_up_kind: Literal["WORK_ORDER", "INSPECTION"] | None = None
    follow_up_description: str | None = Field(default=None, min_length=10, max_length=1000)
    follow_up_unit_id: int | None = Field(default=None, ge=1)

    @field_validator("decision_note")
    @classmethod
    def clean_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Board decision note required")
        return value.strip()

    @model_validator(mode="after")
    def enforce_complete_submission(self):
        if self.offline_meeting_on is not None:
            if not self.decision_maker_seat_id or not self.supporting_attachment_id:
                raise ValueError("Offline board decisions require decision maker and supporting private record.")
        elif self.decision_maker_seat_id is not None or self.supporting_attachment_id is not None:
            raise ValueError("Offline decision maker and supporting record require an offline meeting date.")
        if self.decision == "DENIED" and (
            self.fee is not None or self.follow_up_kind is not None
        ):
            raise ValueError("Denied applications cannot create approval fees or follow-ups.")
        if (self.follow_up_kind is None) != (self.follow_up_description is None):
            raise ValueError("Follow-up kind and description must be supplied together.")
        if self.follow_up_unit_id is not None and self.follow_up_kind != "WORK_ORDER":
            raise ValueError("Only a work-order follow-up accepts an existing unit.")
        return self


class HOAARCDecisionOut(BaseModel):
    id: int
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str
    board_seat_id: int
    decision_maker_seat_id: int
    decided_on: date
    record_method: Literal["DIRECT", "OFFLINE"]
    supporting_attachment_id: int | None = None
    decided_at: datetime
    member_charge_id: int | None = None
    member_charge_amount: Decimal | None = None
    member_charge_due_on: date | None = None
    fee_gl_transaction_id: int | None = None
    fee_reversal_transaction_id: int | None = None
    follow_up_id: int | None = None
    follow_up_kind: str | None = None
    existing_work_order_id: int | None = None
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
