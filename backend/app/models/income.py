# ============================================================
# models/income.py
# ------------------------------------------------------------
# Property income. Every dollar flowing IN.
# Categories: rent, application_fee, late_fee, pet_rent, other.
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
    Numeric,
    Text,
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class IncomeCategory(str, enum.Enum):
    RENT = "rent"
    APPLICATION_FEE = "application_fee"
    LATE_FEE = "late_fee"
    PET_RENT = "pet_rent"
    SECURITY_DEPOSIT = "security_deposit"
    PET_DEPOSIT = "pet_deposit"
    UTILITY_REIMBURSEMENT = "utility_reimbursement"
    OTHER = "other"


class IncomeSource(str, enum.Enum):
    MANUAL = "manual"
    APPLICATION = "application"
    RENT_PAYMENT = "rent_payment"
    STRIPE = "stripe"
    OTHER = "other"


class PropertyIncome(Base):
    __tablename__ = "property_income"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    category = Column(SqlEnum(IncomeCategory), nullable=False, default=IncomeCategory.OTHER)
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(500), nullable=False)
    income_date = Column(Date, nullable=False)

    # Who paid (denormalized for quick reporting)
    payer_name = Column(String(255), nullable=True)
    payer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Where it came from
    source = Column(SqlEnum(IncomeSource), nullable=False, default=IncomeSource.MANUAL)
    source_id = Column(Integer, nullable=True)  # link to application, payment, etc.

    notes = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PropertyIncome {self.category.value} ${self.amount}>"