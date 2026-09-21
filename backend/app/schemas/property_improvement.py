# ============================================================
# property_improvement.py (schemas)
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class PropertyImprovementCreateIn(BaseModel):
    property_id: int
    improvement_date: date
    description: str = Field(..., min_length=1, max_length=500)
    cost: Optional[Decimal] = None
    contractor: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=60)
    warranty_expires: Optional[date] = None
    notes: Optional[str] = None


class PropertyImprovementUpdateIn(BaseModel):
    improvement_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    cost: Optional[Decimal] = None
    contractor: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=60)
    warranty_expires: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    delete_reason: Optional[str] = None


class PropertyImprovementOut(BaseModel):
    id: int
    organization_id: int
    property_id: int
    improvement_date: date
    description: str
    cost: Optional[Decimal] = None
    contractor: Optional[str] = None
    category: Optional[str] = None
    warranty_expires: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool
    delete_reason: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PropertyImprovementListOut(BaseModel):
    items: List[PropertyImprovementOut]
    total: int