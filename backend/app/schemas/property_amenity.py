# ============================================================
# property_amenity.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for Property Amenities.
# ============================================================

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PropertyAmenityCreateIn(BaseModel):
    property_id: int
    name: str = Field(..., min_length=1, max_length=120)
    category: Optional[str] = Field(None, max_length=60)
    notes: Optional[str] = None


class PropertyAmenityUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    category: Optional[str] = Field(None, max_length=60)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyAmenityOut(BaseModel):
    id: int
    organization_id: int
    property_id: int
    name: str
    category: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PropertyAmenityListOut(BaseModel):
    items: List[PropertyAmenityOut]
    total: int