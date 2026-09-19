# ============================================================
# schemas/property.py
# ------------------------------------------------------------
# Shapes for data going in and out of the API for:
#   - Properties
#   - Units
# ============================================================

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.property import PropertyType


# ============================================================
# PROPERTY SCHEMAS
# ============================================================

class PropertyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    property_type: PropertyType = PropertyType.MULTI_FAMILY
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: Optional[str] = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=50)
    zip_code: str = Field(..., min_length=1, max_length=20)
    country: str = "USA"
    year_built: Optional[int] = None
    notes: Optional[str] = None


class PropertyCreate(PropertyBase):
    """What the client sends to create a property."""
    organization_id: int


class PropertyUpdate(BaseModel):
    """All fields optional — send only what you want to change."""
    name: Optional[str] = None
    property_type: Optional[PropertyType] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    year_built: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyOut(PropertyBase):
    """What the API returns for a property."""
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# UNIT SCHEMAS
# ============================================================

class UnitBase(BaseModel):
    unit_number: str = Field(..., min_length=1, max_length=50)
    bedrooms: int = Field(0, ge=0)
    bathrooms: Decimal = Field(Decimal("0.0"), ge=0)
    square_feet: Optional[int] = None
    monthly_rent: Decimal = Field(Decimal("0.00"), ge=0)
    security_deposit: Optional[Decimal] = None


class UnitCreate(UnitBase):
    """What the client sends to create a unit."""
    pass  # property_id comes from the URL


class UnitUpdate(BaseModel):
    unit_number: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    square_feet: Optional[int] = None
    monthly_rent: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None


class UnitOut(UnitBase):
    """What the API returns for a unit."""
    id: int
    property_id: int
    is_available: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# NESTED OUTPUT (property + its units together)
# ============================================================

class PropertyWithUnits(PropertyOut):
    """Property with its units included."""
    units: List[UnitOut] = []