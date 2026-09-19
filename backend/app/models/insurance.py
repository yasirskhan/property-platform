# ============================================================
# models/insurance.py
# ------------------------------------------------------------
# Insurance policies for a property.
# A property can have multiple policies (hazard, flood, etc.).
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
# POLICY TYPE
# ------------------------------------------------------------
class PolicyType(str, enum.Enum):
    HAZARD = "hazard"
    FLOOD = "flood"
    UMBRELLA = "umbrella"
    LIABILITY = "liability"
    EARTHQUAKE = "earthquake"
    WINDSTORM = "windstorm"
    OTHER = "other"


# ------------------------------------------------------------
# PREMIUM FREQUENCY
# ------------------------------------------------------------
class PremiumFrequency(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    OTHER = "other"


# ------------------------------------------------------------
# PROPERTY INSURANCE
# ------------------------------------------------------------
class PropertyInsurance(Base):
    __tablename__ = "property_insurance"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    policy_type = Column(SqlEnum(PolicyType), nullable=False, default=PolicyType.HAZARD)
    provider = Column(String(255), nullable=False)
    policy_number = Column(String(100), nullable=True)

    coverage_amount = Column(Numeric(12, 2), nullable=True)
    deductible = Column(Numeric(12, 2), nullable=True)
    premium_amount = Column(Numeric(10, 2), nullable=True)
    premium_frequency = Column(
        SqlEnum(PremiumFrequency), nullable=False, default=PremiumFrequency.ANNUAL
    )

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    agent_name = Column(String(255), nullable=True)
    agent_phone = Column(String(50), nullable=True)
    agent_email = Column(String(255), nullable=True)

    document_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PropertyInsurance {self.provider} ({self.policy_type.value})>"