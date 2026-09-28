"""Fixed annual 8609-A staff reference statuses. No claims or tax calculations."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

AllocationCategory = Literal["BUILDING_OR_ACQUISITION", "REHABILITATION"]
Readiness = Literal["NOT_RECORDED", "FOLLOW_UP_NEEDED", "REFERENCE_IDENTIFIED"]


class Affordable8609AnnualIn(BaseModel):
    tax_year: int = Field(ge=1987, le=2100)
    allocation_category: AllocationCategory
    status: Readiness


class Affordable8609AnnualOut(Affordable8609AnnualIn):
    model_config = ConfigDict(from_attributes=True)
    building_id: int
    updated_at: datetime | None = None
