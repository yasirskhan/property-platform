"""Staff-proposed recipient is not a legal payer or notice service."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOAViolationRecipientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    contact_link_id: int = Field(ge=1)


class HOAViolationRecipientOut(BaseModel):
    id: int
    case_id: int
    property_id: int
    contact_link_id: int
    contact_name: str
    matched_user_id: int
    updated_at: datetime
    status: Literal["STAFF_LINKED_VERIFIED_LOGIN"] = "STAFF_LINKED_VERIFIED_LOGIN"
    legal_recipient_certified: Literal[False] = False
    notice_delivery_enabled: Literal[False] = False
    member_liability_verified: Literal[False] = False
