"""Staff appeal intake and direct association board disposition."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAFineAppealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    received_on: date
    appeal_reason: str = Field(min_length=3, max_length=2000)
    supporting_attachment_id: int | None = Field(default=None, ge=1)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("appeal_reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Appeal reason required.")
        return value


class HOAFineAppealDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    result: Literal["UPHELD", "VACATED"]
    decision_note: str = Field(min_length=3, max_length=2000)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("decision_note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Disposition reason required.")
        return value


class HOAFineAppealOut(BaseModel):
    id: int
    case_id: int
    fine_id: int
    member_user_id: int | None
    received_on: date
    appeal_reason: str
    supporting_attachment_id: int | None
    status: Literal["OPEN", "UPHELD", "VACATED"]
    decided_on: date | None
    decision_note: str | None
    decision_board_seat_id: int | None
    accounting_reversal_pending: bool
    recorded_at: datetime
    board_disposition_direct: Literal[True] = True
