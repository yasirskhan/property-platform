# ============================================================
# schemas/property.py
# ------------------------------------------------------------
# Shapes for property and unit data in/out of the API.
# ============================================================

from datetime import datetime, date
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
    year_renovated: Optional[int] = None
    square_feet: Optional[int] = None
    stories: Optional[int] = None
    parking_spaces: Optional[int] = None
    parking_type: Optional[str] = None
    estimated_rent: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    ownership_status: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class PropertyCreate(PropertyBase):
    organization_id: int


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    property_type: Optional[PropertyType] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    year_built: Optional[int] = None
    year_renovated: Optional[int] = None
    square_feet: Optional[int] = None
    stories: Optional[int] = None
    parking_spaces: Optional[int] = None
    parking_type: Optional[str] = None
    estimated_rent: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    ownership_status: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyOut(PropertyBase):
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
    pet_deposit: Optional[Decimal] = None
    pet_rent: Optional[Decimal] = None
    application_fee: Optional[Decimal] = None
    admin_fee: Optional[Decimal] = None
    available_from: Optional[date] = None
    lease_term_months: Optional[int] = None
    is_listed: bool = False


class UnitCreate(UnitBase):
    pass


class UnitUpdate(BaseModel):
    unit_number: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    square_feet: Optional[int] = None
    monthly_rent: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    pet_deposit: Optional[Decimal] = None
    pet_rent: Optional[Decimal] = None
    application_fee: Optional[Decimal] = None
    admin_fee: Optional[Decimal] = None
    is_available: Optional[bool] = None
    available_from: Optional[date] = None
    lease_term_months: Optional[int] = None
    is_listed: Optional[bool] = None
    is_active: Optional[bool] = None


class UnitOut(UnitBase):
    id: int
    property_id: int
    is_available: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# NESTED OUTPUT
# ============================================================

class PropertyWithUnits(PropertyOut):
    units: List[UnitOut] = []