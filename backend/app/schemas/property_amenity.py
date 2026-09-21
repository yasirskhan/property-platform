# ============================================================
# property_amenity.py (schemas)
# ============================================================

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


AVAILABILITY_STATUSES = ("INCLUDED", "EXTRA_FEE", "NOT_AVAILABLE")


class PropertyAmenityCreateIn(BaseModel):
    property_id: int
    name: str = Field(..., min_length=1, max_length=120)
    category: Optional[str] = Field(None, max_length=60)
    notes: Optional[str] = None
    fee_amount: Optional[Decimal] = None
    availability_status: Optional[str] = Field(None, max_length=30)

    @field_validator("availability_status")
    @classmethod
    def _valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        up = v.strip().upper()
        if up not in AVAILABILITY_STATUSES:
            raise ValueError(
                f"availability_status must be one of {AVAILABILITY_STATUSES}"
            )
        return up


class PropertyAmenityUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    category: Optional[str] = Field(None, max_length=60)
    notes: Optional[str] = None
    fee_amount: Optional[Decimal] = None
    availability_status: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None
    delete_reason: Optional[str] = None

    @field_validator("availability_status")
    @classmethod
    def _valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        up = v.strip().upper()
        if up not in AVAILABILITY_STATUSES:
            raise ValueError(
                f"availability_status must be one of {AVAILABILITY_STATUSES}"
            )
        return up


class PropertyAmenityOut(BaseModel):
    id: int
    organization_id: int
    property_id: int
    name: str
    category: Optional[str] = None
    notes: Optional[str] = None
    fee_amount: Optional[Decimal] = None
    availability_status: Optional[str] = None
    is_active: bool
    delete_reason: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PropertyAmenityListOut(BaseModel):
    items: List[PropertyAmenityOut]
    total: int