# ============================================================
# models/expense.py
# ------------------------------------------------------------
# Property expenses. Every cost of running a property.
# Sources: manual entry, insurance premiums, mortgage,
# taxes, utilities, repairs.
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


# ------------------------------------------------------------
# EXPENSE CATEGORY
# ------------------------------------------------------------
class ExpenseCategory(str, enum.Enum):
    INSURANCE = "insurance"
    MORTGAGE = "mortgage"
    TAXES = "taxes"
    UTILITIES = "utilities"
    REPAIRS = "repairs"
    MAINTENANCE = "maintenance"
    MANAGEMENT = "management"
    HOA = "hoa"
    LEGAL = "legal"
    MARKETING = "marketing"
    SUPPLIES = "supplies"
    OTHER = "other"


# ------------------------------------------------------------
# EXPENSE SOURCE
# ------------------------------------------------------------
class ExpenseSource(str, enum.Enum):
    MANUAL = "manual"           # entered by hand
    INSURANCE = "insurance"     # auto-created from property_insurance
    MORTGAGE = "mortgage"       # auto-created from mortgage payment
    TAX = "tax"                 # auto-created from property_tax_payment
    UTILITY = "utility"         # auto-created from utility_bill
    IMPROVEMENT = "improvement" # auto-created from improvement
    OTHER = "other"


# ------------------------------------------------------------
# PROPERTY EXPENSE
# ------------------------------------------------------------
class PropertyExpense(Base):
    __tablename__ = "property_expenses"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    category = Column(SqlEnum(ExpenseCategory), nullable=False, default=ExpenseCategory.OTHER)
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(500), nullable=False)
    expense_date = Column(Date, nullable=False)

    # Where it came from
    source = Column(SqlEnum(ExpenseSource), nullable=False, default=ExpenseSource.MANUAL)
    source_id = Column(Integer, nullable=True)  # ID in the source table

    notes = Column(Text, nullable=True)
    receipt_url = Column(String(500), nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PropertyExpense {self.category.value} ${self.amount}>"