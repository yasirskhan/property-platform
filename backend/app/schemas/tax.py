# ============================================================
# schemas/tax.py
# ============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.tax import TaxType, PaymentFrequency


class PropertyTaxBase(BaseModel):
    tax_authority: str = Field(..., min_length=1, max_length=255)
    tax_type: TaxType = TaxType.COUNTY
    parcel_number: Optional[str] = None
    assessed_value: Optional[Decimal] = None
    tax_rate_percent: Optional[Decimal] = None
    annual_amount: Optional[Decimal] = None
    payment_frequency: PaymentFrequency = PaymentFrequency.ANNUAL
    payment_amount: Optional[Decimal] = None
    next_due_date: Optional[date] = None
    escrow_included: bool = False
    notes: Optional[str] = None


class PropertyTaxCreate(PropertyTaxBase):
    pass


class PropertyTaxUpdate(BaseModel):
    tax_authority: Optional[str] = None
    tax_type: Optional[TaxType] = None
    parcel_number: Optional[str] = None
    assessed_value: Optional[Decimal] = None
    tax_rate_percent: Optional[Decimal] = None
    annual_amount: Optional[Decimal] = None
    payment_frequency: Optional[PaymentFrequency] = None
    payment_amount: Optional[Decimal] = None
    next_due_date: Optional[date] = None
    escrow_included: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class PropertyTaxOut(PropertyTaxBase):
    id: int
    property_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# PAYMENTS
# ------------------------------------------------------------
class TaxPaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    paid_at: date
    period: Optional[str] = None
    confirmation_number: Optional[str] = None
    receipt_url: Optional[str] = None
    is_paid_from_escrow: bool = False
    notes: Optional[str] = None


class TaxPaymentCreate(TaxPaymentBase):
    pass


class TaxPaymentOut(TaxPaymentBase):
    id: int
    tax_id: int
    created_by_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PropertyTaxWithPayments(PropertyTaxOut):
    payments: List[TaxPaymentOut] = []