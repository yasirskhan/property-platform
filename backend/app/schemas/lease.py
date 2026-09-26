# ============================================================
# schemas/lease.py
# ------------------------------------------------------------
# Shapes for lease, invoice, and payment data going in/out
# of the API.
# ============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.lease import LeaseStatus, InvoiceStatus, PaymentMethod


# ============================================================
# LEASE SCHEMAS
# ============================================================

class LeaseBase(BaseModel):
    unit_id: int
    tenant_id: int
    start_date: date
    end_date: date
    monthly_rent: Decimal = Field(..., ge=0)
    security_deposit: Decimal = Field(Decimal("0.00"), ge=0)
    security_deposit_gl_account_id: Optional[int] = None
    due_day: int = Field(1, ge=1, le=28)
    notes: Optional[str] = None


class LeaseCreate(LeaseBase):
    """What the client sends to create a lease."""
    status: LeaseStatus = LeaseStatus.DRAFT


class LeaseUpdate(BaseModel):
    """All fields optional — send only what you want to change."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    monthly_rent: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    security_deposit_gl_account_id: Optional[int] = None
    due_day: Optional[int] = None
    status: Optional[LeaseStatus] = None
    notes: Optional[str] = None


class LeaseOut(LeaseBase):
    """What the API returns for a lease."""
    id: int
    status: LeaseStatus
    signed_at: Optional[datetime] = None
    signed_by_tenant: bool
    signed_by_manager: bool
    document_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# INVOICE SCHEMAS
# ============================================================

class RentInvoiceBase(BaseModel):
    lease_id: int
    period_start: date
    period_end: date
    due_date: date
    amount_due: Decimal = Field(..., ge=0)
    late_fee: Decimal = Field(Decimal("0.00"), ge=0)


class RentInvoiceCreate(RentInvoiceBase):
    """What the client sends to create an invoice."""
    pass


class RentInvoiceOut(RentInvoiceBase):
    """What the API returns for an invoice."""
    id: int
    amount_paid: Decimal
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# PAYMENT SCHEMAS
# ============================================================

class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    method: PaymentMethod = PaymentMethod.ACH
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    """What the client sends to record a payment."""
    pass


class PaymentOut(PaymentBase):
    """What the API returns for a payment."""
    id: int
    invoice_id: int
    paid_at: datetime
    external_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# NESTED OUTPUT (lease with its invoices)
# ============================================================

class LeaseWithInvoices(LeaseOut):
    """Lease with its invoices included."""
    invoices: List[RentInvoiceOut] = []

    
# ============================================================
# STRIPE SCHEMAS
# ============================================================

class StripeCheckoutRequest(BaseModel):
    """What the client sends to start a Stripe checkout session."""
    success_url: str = "http://localhost:3000/payment/success"
    cancel_url: str = "http://localhost:3000/payment/cancel"


class StripeCheckoutResponse(BaseModel):
    """What the API returns when a checkout session is created."""
    checkout_url: str
    session_id: str