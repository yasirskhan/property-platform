# ============================================================
# models/lease.py
# ------------------------------------------------------------
# Tables for:
#   - Leases (the contract between a tenant and a unit)
#   - RentInvoices (monthly bills generated from a lease)
#   - Payments (recorded payments against invoices)
# ============================================================

import enum
from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
    Boolean,
    Numeric,
    Text,
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ------------------------------------------------------------
# LEASE STATUS
# ------------------------------------------------------------
class LeaseStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    CANCELLED = "cancelled"


# ------------------------------------------------------------
# INVOICE STATUS
# ------------------------------------------------------------
class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    DUE = "due"
    PAID = "paid"
    PARTIAL = "partial"
    VOID = "void"


# ------------------------------------------------------------
# PAYMENT METHOD
# ------------------------------------------------------------
class PaymentMethod(str, enum.Enum):
    ACH = "ach"
    CARD = "card"
    CHECK = "check"
    CASH = "cash"
    OTHER = "other"


# ------------------------------------------------------------
# LEASE
# ------------------------------------------------------------
class Lease(Base):
    __tablename__ = "leases"

    id = Column(Integer, primary_key=True, index=True)

    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    monthly_rent = Column(Numeric(10, 2), nullable=False)
    security_deposit = Column(Numeric(10, 2), nullable=False, default=0.00)
    # Optional deposit liability selected during move-in. Owner-held
    # deposits point to an org-approved AccountingKeyAccount.
    security_deposit_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    due_day = Column(Integer, nullable=False, default=1)

    status = Column(SqlEnum(LeaseStatus), nullable=False, default=LeaseStatus.DRAFT)

    signed_at = Column(DateTime, nullable=True)
    signed_by_tenant = Column(Boolean, default=False)
    signed_by_manager = Column(Boolean, default=False)

    document_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    invoices = relationship("RentInvoice", back_populates="lease", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lease id={self.id} unit={self.unit_id} tenant={self.tenant_id} status={self.status.value}>"


# ------------------------------------------------------------
# RENT INVOICE
# ------------------------------------------------------------
class RentInvoice(Base):
    __tablename__ = "rent_invoices"

    id = Column(Integer, primary_key=True, index=True)

    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False, index=True)

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0.00)

    late_fee = Column(Numeric(10, 2), nullable=False, default=0.00)

    status = Column(SqlEnum(InvoiceStatus), nullable=False, default=InvoiceStatus.PENDING)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lease = relationship("Lease", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RentInvoice id={self.id} lease={self.lease_id} due={self.due_date} status={self.status.value}>"


# ------------------------------------------------------------
# PAYMENT
# ------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    invoice_id = Column(Integer, ForeignKey("rent_invoices.id"), nullable=False, index=True)

    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(SqlEnum(PaymentMethod), nullable=False, default=PaymentMethod.ACH)
    paid_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    external_id = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("RentInvoice", back_populates="payments")

    def __repr__(self):
        return f"<Payment id={self.id} invoice={self.invoice_id} amount={self.amount}>" 