"""Only fixed staff follow-up statuses; not signed 8609 certification or tax amounts."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

Readiness = Literal["NOT_RECORDED", "FOLLOW_UP_NEEDED", "REFERENCE_IDENTIFIED"]


class Affordable8609ReadinessIn(BaseModel):
    status: Readiness


class Affordable8609ReadinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    building_id: int
    status: Readiness
    updated_at: datetime | None = None
