"""Deliberately do not confuse an SMTP handoff with recipient delivery or legal service."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Status = Literal["PENDING", "SENDING", "FAILED", "TEST_ONLY", "SMTP_ACCEPTED"]


class HOADocumentSendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    contact_link_id: int = Field(ge=1)
    request_key: str = Field(min_length=12, max_length=64)


class HOADocumentRecipientOut(BaseModel):
    contact_link_id: int
    contact_name: str


class HOADocumentDeliveryOut(BaseModel):
    id: int
    evidence_id: int
    contact_link_id: int
    status: Status
    attempt_count: int
    created_at: datetime
    accepted_at: datetime | None
    file_sha256: str
    email_attachment_included: bool
    recipient_delivery_confirmed: Literal[False] = False
    legally_served: Literal[False] = False
