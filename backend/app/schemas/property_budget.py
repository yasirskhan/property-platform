"""Property budget entry and read-only output contracts."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PropertyBudgetUpsertIn(BaseModel):
    property_id: int = Field(ge=1)
    gl_account_id: int = Field(ge=1)
    calendar_year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class PropertyBudgetOut(PropertyBudgetUpsertIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    updated_at: datetime
