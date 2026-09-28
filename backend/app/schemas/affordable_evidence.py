"""Fixed staff evidence-index categories; no PII, household data, or certifications."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

Category = Literal["AGENCY_GUIDANCE", "PROGRAM_AGREEMENT", "PROPERTY_RECORD_INDEX", "INSPECTION_COORDINATION"]
Readiness = Literal["NOT_RECORDED", "FOLLOW_UP_NEEDED", "REFERENCE_IDENTIFIED"]


class AffordableEvidenceIn(BaseModel):
    category: Category
    status: Readiness
    staff_follow_up_on: date | None = None


class AffordableEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category: Category
    status: Readiness
    staff_follow_up_on: date | None
    updated_at: datetime | None = None
