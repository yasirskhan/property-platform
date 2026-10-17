"""CRM workflow fields only; identity stays in existing Contacts."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

Stage = Literal["NEW", "CONTACTED", "TOUR_SCHEDULED", "APPLIED", "CLOSED"]
class ProspectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    contact_id: int = Field(ge=1)
    stage: Stage = "NEW"
    source: str = Field(default="OTHER", min_length=1, max_length=60)
    next_follow_up: date | None = None

class ProspectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Stage | None = None
    source: str | None = Field(default=None, min_length=1, max_length=60)
    next_follow_up: date | None = None

class ProspectOut(ProspectIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    contact_name: str
    contact_email: str | None = None

class ProspectList(BaseModel):
    items: list[ProspectOut]
    total: int
