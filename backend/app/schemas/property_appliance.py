# ============================================================
# property_appliance.py (schemas)
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


APPLIANCE_CONDITIONS = ("NEW", "GOOD", "FAIR", "NEEDS_REPAIR")


class PropertyApplianceCreateIn(BaseModel):
    property_id: int
    name: str = Field(..., min_length=1, max_length=120)
    brand: Optional[str] = Field(None, max_length=120)
    model_number: Optional[str] = Field(None, max_length=120)
    serial_number: Optional[str] = Field(None, max_length=120)
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = None
    warranty_expires: Optional[date] = None
    condition: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = None

    @field_validator("condition")
    @classmethod
    def _valid_condition(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        up = v.strip().upper()
        if up not in APPLIANCE_CONDITIONS:
            raise ValueError(
                f"condition must be one of {APPLIANCE_CONDITIONS}"
            )
        return up


class PropertyApplianceUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    brand: Optional[str] = Field(None, max_length=120)
    model_number: Optional[str] = Field(None, max_length=120)
    serial_number: Optional[str] = Field(None, max_length=120)
    purchase_date: Optional[date] = None
    purchase_price: Optional[Decimal] = None
    warranty_expires: Optional[date] = None
    condition: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    delete_reason: Optional[str] = None

    @field_validator("condition")
    @classmethod
    def _valid_condition(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        up = v.strip().upper()
        if up not in APPLIANCE_CONDITIONS:
            raise ValueError(
                f"condition must be one of {APPLIANCE_CONDITIONS}"
            )
        return up


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
    condition: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    delete_reason: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PropertyApplianceListOut(BaseModel):
    items: List[PropertyApplianceOut]
    total: int