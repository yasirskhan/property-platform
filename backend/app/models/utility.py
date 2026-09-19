# ============================================================
# models/utility.py
# ------------------------------------------------------------
# Utility companies for a property, bills, and trash schedule.
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
# UTILITY TYPE
# ------------------------------------------------------------
class UtilityType(str, enum.Enum):
    ELECTRIC = "electric"
    GAS = "gas"
    WATER = "water"
    SEWER = "sewer"
    TRASH = "trash"
    INTERNET = "internet"
    CABLE = "cable"
    OTHER = "other"


# ------------------------------------------------------------
# WHO PAYS
# ------------------------------------------------------------
class PaidBy(str, enum.Enum):
    TENANT = "tenant"
    OWNER = "owner"
    INCLUDED_IN_RENT = "included_in_rent"
    SHARED = "shared"


# ------------------------------------------------------------
# TRASH PICKUP TYPE
# ------------------------------------------------------------
class PickupType(str, enum.Enum):
    TRASH = "trash"
    RECYCLING = "recycling"
    YARD_WASTE = "yard_waste"
    BULK = "bulk"


# ------------------------------------------------------------
# PROPERTY UTILITY
# ------------------------------------------------------------
class PropertyUtility(Base):
    __tablename__ = "property_utilities"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    utility_type = Column(SqlEnum(UtilityType), nullable=False, default=UtilityType.OTHER)
    company_name = Column(String(255), nullable=False)
    company_phone = Column(String(50), nullable=True)
    company_website = Column(String(255), nullable=True)

    paid_by = Column(SqlEnum(PaidBy), nullable=False, default=PaidBy.TENANT)
    account_number = Column(String(100), nullable=True)  # tenant hidden
    account_holder_name = Column(String(255), nullable=True)  # tenant hidden

    setup_instructions = Column(Text, nullable=True)  # shown to tenant
    internal_notes = Column(Text, nullable=True)  # tenant hidden

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bills = relationship("UtilityBill", back_populates="utility", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PropertyUtility {self.company_name} ({self.utility_type.value})>"


# ------------------------------------------------------------
# UTILITY BILL (owner-paid only)
# ------------------------------------------------------------
class UtilityBill(Base):
    __tablename__ = "utility_bills"

    id = Column(Integer, primary_key=True, index=True)
    utility_id = Column(Integer, ForeignKey("property_utilities.id"), nullable=False, index=True)

    billing_period_start = Column(Date, nullable=True)
    billing_period_end = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    paid_at = Column(Date, nullable=True)

    invoice_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    utility = relationship("PropertyUtility", back_populates="bills")

    def __repr__(self):
        return f"<UtilityBill utility={self.utility_id} amount={self.amount}>"


# ------------------------------------------------------------
# TRASH PICKUP SCHEDULE
# ------------------------------------------------------------
class TrashPickupSchedule(Base):
    __tablename__ = "trash_pickup_schedule"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    pickup_type = Column(SqlEnum(PickupType), nullable=False, default=PickupType.TRASH)
    day_of_week = Column(String(20), nullable=False)  # monday, tuesday, etc.
    frequency = Column(String(20), nullable=False, default="weekly")  # weekly, biweekly, monthly
    time_window = Column(String(100), nullable=True)  # "Before 7am"
    notes = Column(Text, nullable=True)  # tenant visible

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TrashPickupSchedule {self.pickup_type.value} {self.day_of_week}>"