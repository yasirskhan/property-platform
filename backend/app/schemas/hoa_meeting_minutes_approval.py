"""Board-authenticated approval of an exact previously prepared minutes revision."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HOAMinutesBoardApprovalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    minutes_revision: int = Field(ge=1)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    approval_note: str = Field(min_length=3, max_length=1500)

    @field_validator("approval_note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Board approval note must not be blank.")
        return value.strip()


class HOAMinutesBoardApprovalOut(BaseModel):
    id: int
    meeting_draft_id: int
    minutes_draft_id: int
    property_id: int
    minutes_revision: int
    content_sha256: str
    board_seat_id: int
    approved_by_user_id: int
    approved_at: datetime
    approval_note: str
    status: Literal["BOARD_MEMBER_APPROVED"] = "BOARD_MEMBER_APPROVED"
    quorum_certified: Literal[False] = False
    full_board_vote_certified: Literal[False] = False
    financial_posting: Literal[False] = False
