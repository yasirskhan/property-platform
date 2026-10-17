# ============================================================
# models/tax.py
# ------------------------------------------------------------
# Property tax records and payments.
# One property can have multiple tax authorities (county,
# school district, municipality, etc.).
# ============================================================

import enum
from datetime import datetime

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
# TAX TYPES
# ------------------------------------------------------------
class TaxType(str, enum.Enum):
    COUNTY = "county"
    SCHOOL = "school"
    MUNICIPAL = "municipal"
    SPECIAL_DISTRICT = "special_district"
    OTHER = "other"


# ------------------------------------------------------------
# PAYMENT FREQUENCY
# ------------------------------------------------------------
class PaymentFrequency(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    OTHER = "other"


# ------------------------------------------------------------
# PROPERTY TAX
# ------------------------------------------------------------
class PropertyTax(Base):
    __tablename__ = "property_taxes"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    # --- Authority ---
    tax_authority = Column(String(255), nullable=False)  # "Travis County"
    tax_type = Column(SqlEnum(TaxType), nullable=False, default=TaxType.COUNTY)
    parcel_number = Column(String(100), nullable=True)

    # --- Amounts ---
    assessed_value = Column(Numeric(12, 2), nullable=True)
    tax_rate_percent = Column(Numeric(6, 4), nullable=True)
    annual_amount = Column(Numeric(12, 2), nullable=True)

    # --- Payment schedule ---
    payment_frequency = Column(SqlEnum(PaymentFrequency), nullable=False, default=PaymentFrequency.ANNUAL)
    payment_amount = Column(Numeric(10, 2), nullable=True)
    next_due_date = Column(Date, nullable=True)
    escrow_included = Column(Boolean, default=False)

    # --- Status ---
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = relationship("PropertyTaxPayment", back_populates="tax", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PropertyTax {self.tax_authority} ({self.tax_type.value})>"


# ------------------------------------------------------------
# PROPERTY TAX PAYMENT
# ------------------------------------------------------------
class PropertyTaxPayment(Base):
    __tablename__ = "property_tax_payments"

    id = Column(Integer, primary_key=True, index=True)

    tax_id = Column(Integer, ForeignKey("property_taxes.id"), nullable=False, index=True)

    amount = Column(Numeric(10, 2), nullable=False)
    paid_at = Column(Date, nullable=False)
    period = Column(String(50), nullable=True)  # "2026 Q1" or "2026"
    confirmation_number = Column(String(100), nullable=True)
    receipt_url = Column(String(500), nullable=True)
    is_paid_from_escrow = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tax = relationship("PropertyTax", back_populates="payments")

    def __repr__(self):
        return f"<PropertyTaxPayment tax={self.tax_id} amount={self.amount}>"