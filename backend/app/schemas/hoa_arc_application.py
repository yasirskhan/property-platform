"""Generic HOA ARC application/review workflow with legally effective decisions disabled."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ARCStatus = Literal[
    "SUBMITTED", "UNDER_REVIEW", "MORE_INFO_REQUESTED",
    "INFO_RECEIVED", "READY_FOR_DECISION", "DECISION_PREPARED",
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
    legal_decision_effective: Literal[False] = False
    governing_authority_verified: Literal[False] = False
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
    event_type: ARCEventType | Literal["APPLICATION_SUBMITTED"]
    staff_note: str | None
    created_at: datetime
    legal_effect: Literal[False] = False


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
