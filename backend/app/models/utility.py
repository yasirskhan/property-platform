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
    UniqueConstraint,
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
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bills = relationship("UtilityBill", back_populates="utility", cascade="all, delete-orphan")
    meter_readings = relationship(
        "UtilityMeterReading", back_populates="utility", cascade="all, delete-orphan"
    )
    allocation_rule_revisions = relationship(
        "UtilityAllocationRuleRevision",
        back_populates="utility",
        cascade="all, delete-orphan",
    )
    allocation_snapshots = relationship(
        "UtilityAllocationSnapshot",
        back_populates="utility",
        cascade="all, delete-orphan",
    )

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
# UTILITY METER READING (Phase 4.9 RUBs raw input)
# ------------------------------------------------------------
class UtilityMeterReading(Base):
    __tablename__ = "utility_meter_readings"

    id = Column(Integer, primary_key=True, index=True)
    utility_id = Column(
        Integer, ForeignKey("property_utilities.id"), nullable=False, index=True
    )
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True, index=True)

    meter_identifier = Column(String(120), nullable=False)
    reading_date = Column(Date, nullable=False, index=True)
    reading_value = Column(Numeric(18, 6), nullable=False)
    unit_of_measure = Column(String(32), nullable=False)

    source = Column(String(16), nullable=False)  # MANUAL | IMPORT
    import_batch_key = Column(String(96), nullable=True, index=True)
    request_key = Column(String(160), nullable=False)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    utility = relationship("PropertyUtility", back_populates="meter_readings")

    __table_args__ = (
        UniqueConstraint(
            "utility_id", "request_key", name="uq_utility_meter_reading_request"
        ),
    )

    def __repr__(self):
        return (
            f"<UtilityMeterReading utility={self.utility_id} "
            f"meter={self.meter_identifier} date={self.reading_date}>"
        )


# ------------------------------------------------------------
# RUBs ALLOCATION RULE REVISION (Phase 4.9 non-posting preview)
# ------------------------------------------------------------
class UtilityAllocationRuleRevision(Base):
    __tablename__ = "utility_allocation_rule_revisions"

    id = Column(Integer, primary_key=True, index=True)
    utility_id = Column(Integer, ForeignKey("property_utilities.id"), nullable=False, index=True)
    revision_number = Column(Integer, nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    basis = Column(String(32), nullable=False)
    unit_inputs_json = Column(Text, nullable=False)
    request_key = Column(String(96), nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT")
    is_authorized = Column(Boolean, nullable=False, default=False)
    authorization_request_key = Column(String(96), nullable=True)
    authorized_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    authorized_at = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    utility = relationship("PropertyUtility", back_populates="allocation_rule_revisions")

    __table_args__ = (
        UniqueConstraint("utility_id", "revision_number", name="uq_utility_allocation_rule_revision"),
        UniqueConstraint("utility_id", "request_key", name="uq_utility_allocation_rule_request"),
    )

    def __repr__(self):
        return (
            f"<UtilityAllocationRuleRevision utility={self.utility_id} "
            f"revision={self.revision_number} basis={self.basis}>"
        )


# ------------------------------------------------------------
# RUBs REVIEWED ALLOCATION SNAPSHOT (Phase 4.9 historical source)
# ------------------------------------------------------------
class UtilityAllocationSnapshot(Base):
    __tablename__ = "utility_allocation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    utility_id = Column(Integer, ForeignKey("property_utilities.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("utility_bills.id"), nullable=False, index=True)
    rule_revision_id = Column(
        Integer,
        ForeignKey("utility_allocation_rule_revisions.id"),
        nullable=False,
        index=True,
    )
    billing_period_start = Column(Date, nullable=False, index=True)
    billing_period_end = Column(Date, nullable=False, index=True)
    bill_amount = Column(Numeric(12, 2), nullable=False)
    basis = Column(String(32), nullable=False)
    unit_inputs_json = Column(Text, nullable=False)
    allocation_items_json = Column(Text, nullable=False)
    allocated_total = Column(Numeric(12, 2), nullable=False)
    remainder_rule = Column(Text, nullable=False)
    request_key = Column(String(96), nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    utility = relationship("PropertyUtility", back_populates="allocation_snapshots")

    __table_args__ = (
        UniqueConstraint(
            "utility_id",
            "request_key",
            name="uq_utility_allocation_snapshot_request",
        ),
    )

    def __repr__(self):
        return (
            f"<UtilityAllocationSnapshot utility={self.utility_id} "
            f"bill={self.bill_id} rule={self.rule_revision_id}>"
        )


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
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TrashPickupSchedule {self.pickup_type.value} {self.day_of_week}>"