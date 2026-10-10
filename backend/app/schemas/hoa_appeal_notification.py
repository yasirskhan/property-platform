"""Explicit, scoped appeal outcome email with transport-only status."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOAAppealNotificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    template_id: int = Field(ge=1)
    request_key: str = Field(min_length=12, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class HOAAppealNotificationOut(BaseModel):
    id: int
    appeal_id: int
    template_id: int
    outcome: Literal["UPHELD", "VACATED"]
    status: Literal["PENDING", "SENDING", "FAILED", "TEST_ONLY", "SMTP_ACCEPTED"]
    attempt_count: int
    smtp_accepted_at: datetime | None
    actual_delivery_confirmed: Literal[False] = False
    legally_served: Literal[False] = False
    accounting_modified: Literal[False] = False


class HOAAppealTemplateOut(BaseModel):
    id: int
    title: str
    subject: str
    body: str
