# ============================================================
# property_appliance.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for Property Appliances.
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class PropertyApplianceCreateIn(BaseModel):
    property_id: int
    name: str = Field(..., min_length=1, max_length=120)
    brand: Optional[str] = Field(None, max_length=120)
    model_number: Optional[str] = Field(None, max_length=120)
    serial_number: Optional[str] = Field(None, max_length=120)
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = None
    warranty_expires: Optional[date] = None
    notes: Optional[str] = None


class PropertyApplianceUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    brand: Optional[str] = Field(None, max_length=120)
    model_number: Optional[str] = Field(None, max_length=120)
    serial_number: Optional[str] = Field(None, max_length=120)
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = None
    warranty_expires: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyApplianceOut(BaseModel):
    id: int
    organization_id: int
    property_id: int
    name: str
    brand: Optional[str] = None
    model_number: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = None
    warranty_expires: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PropertyApplianceListOut(BaseModel):
    items: List[PropertyApplianceOut]
    total: int