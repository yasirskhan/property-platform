"""Read-only staff interest display; no priority, protected trait or eligibility data."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AffordableInterestIn(BaseModel):
    prospect_id: int = Field(ge=1)


class AffordableInterestOut(BaseModel):
    id: int
    program_id: int
    prospect_id: int
    contact_name: str
    recorded_at: datetime
