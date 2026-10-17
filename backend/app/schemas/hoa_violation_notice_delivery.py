"""Explicit board-authorized HOA case email transport, not statutory service."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOAViolationNoticeSendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    correspondence_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    request_key: str = Field(min_length=12, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class HOAViolationNoticeDeliveryOut(BaseModel):
    id: int
    correspondence_id: int
    correspondence_revision: int
    policy_revision: int
    status: Literal["PENDING", "SENDING", "TEST_ONLY", "SMTP_ACCEPTED", "FAILED"]
    attempt_count: int
    smtp_accepted_at: datetime | None
    board_seat_id: int
    legally_served: Literal[False] = False
    fine_assessed: Literal[False] = False
    smtp_is_proof_of_receipt: Literal[False] = False
