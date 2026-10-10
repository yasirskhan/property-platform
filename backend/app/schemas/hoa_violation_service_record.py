"""Association-attested actual service record: evidence, dates, privacy."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class HOAServiceRecordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    correspondence_id: int = Field(ge=1)
    correspondence_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    member_user_id: int = Field(ge=1)
    proof_attachment_id: int = Field(ge=1)
    delivery_method: Literal["PERSONAL", "POSTAL", "EMAIL_CONFIRMED", "OTHER"]
    served_on: date
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

class HOAServiceRecordOut(BaseModel):
    id: int
    case_id: int
    correspondence_id: int
    correspondence_revision: int
    policy_revision: int
    member_user_id: int
    proof_attachment_id: int
    delivery_method: str
    served_on: date
    cure_earliest_on: date
    hearing_request_earliest_on: date
    board_seat_id: int
    recorded_at: datetime
    platform_certifies_service: Literal[False] = False
