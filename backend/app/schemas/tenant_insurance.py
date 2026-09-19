# ============================================================
# schemas/tenant_insurance.py
# ============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.tenant_insurance import (
    TenantInsuranceStatus,
    ExtractionStatus,
)


class TenantInsuranceBase(BaseModel):
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_amount: Optional[Decimal] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None


class TenantInsuranceCreate(TenantInsuranceBase):
    lease_id: int


class TenantInsuranceUpdate(BaseModel):
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_amount: Optional[Decimal] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None


class TenantInsuranceOut(TenantInsuranceBase):
    id: int
    lease_id: int
    tenant_id: int
    property_id: int
    status: TenantInsuranceStatus
    extraction_status: ExtractionStatus
    verified_by_id: Optional[int] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantInsuranceVerify(BaseModel):
    """Manager approves or rejects."""
    approve: bool
    rejection_reason: Optional[str] = None