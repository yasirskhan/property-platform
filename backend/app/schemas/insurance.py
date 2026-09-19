# ============================================================
# schemas/insurance.py
# ============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.insurance import PolicyType, PremiumFrequency


class PropertyInsuranceBase(BaseModel):
    policy_type: PolicyType = PolicyType.HAZARD
    provider: str = Field(..., min_length=1, max_length=255)
    policy_number: Optional[str] = None
    coverage_amount: Optional[Decimal] = None
    deductible: Optional[Decimal] = None
    premium_amount: Optional[Decimal] = None
    premium_frequency: PremiumFrequency = PremiumFrequency.ANNUAL
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    agent_email: Optional[str] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None


class PropertyInsuranceCreate(PropertyInsuranceBase):
    pass


class PropertyInsuranceUpdate(BaseModel):
    policy_type: Optional[PolicyType] = None
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_amount: Optional[Decimal] = None
    deductible: Optional[Decimal] = None
    premium_amount: Optional[Decimal] = None
    premium_frequency: Optional[PremiumFrequency] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    agent_email: Optional[str] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyInsuranceOut(PropertyInsuranceBase):
    id: int
    property_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True