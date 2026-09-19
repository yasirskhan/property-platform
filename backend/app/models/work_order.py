# ============================================================
# models/work_order.py
# ------------------------------------------------------------
# Tables for:
#   - WorkOrders (maintenance requests)
#   - WorkOrderUpdates (activity log / comments)
# ============================================================

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Numeric,
    Text,
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ------------------------------------------------------------
# CATEGORIES
# ------------------------------------------------------------
class WorkOrderCategory(str, enum.Enum):
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    APPLIANCE = "appliance"
    GENERAL = "general"
    PEST = "pest"
    CLEANING = "cleaning"
    LANDSCAPING = "landscaping"
    OTHER = "other"


# ------------------------------------------------------------
# PRIORITY
# ------------------------------------------------------------
class WorkOrderPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


# ------------------------------------------------------------
# STATUS
# ------------------------------------------------------------
class WorkOrderStatus(str, enum.Enum):
    SUBMITTED = "submitted"       # tenant just submitted
    ACKNOWLEDGED = "acknowledged" # manager has seen it
    ASSIGNED = "assigned"         # crew assigned
    IN_PROGRESS = "in_progress"   # crew working
    COMPLETED = "completed"       # crew finished, awaiting manager approval
    CLOSED = "closed"             # manager approved and closed
    CANCELLED = "cancelled"       # cancelled (duplicate, no action needed)


# ------------------------------------------------------------
# WORK ORDER
# ------------------------------------------------------------
class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)

    # Who/where
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    # Assigned crew (may be null until assigned)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(SqlEnum(WorkOrderCategory), nullable=False, default=WorkOrderCategory.OTHER)
    priority = Column(SqlEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.MEDIUM)
    status = Column(SqlEnum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.SUBMITTED)

    # Permission to enter unit?
    permission_to_enter = Column(Boolean, default=False)
    entry_notes = Column(Text, nullable=True)  # e.g. "key under mat"

    # Photos (simple JSON string of URLs for now — we'll add file upload later)
    photo_urls = Column(Text, nullable=True)  # comma-separated URLs

    # Costs (filled in when completing)
    labor_cost = Column(Numeric(10, 2), nullable=True)
    materials_cost = Column(Numeric(10, 2), nullable=True)
    total_cost = Column(Numeric(10, 2), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Timestamps for lifecycle stages
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    updates = relationship(
        "WorkOrderUpdate",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderUpdate.created_at",
    )

    def __repr__(self):
        return f"<WorkOrder id={self.id} status={self.status.value} priority={self.priority.value}>"


# ------------------------------------------------------------
# WORK ORDER UPDATE (activity log / comments)
# ------------------------------------------------------------
class WorkOrderUpdate(Base):
    __tablename__ = "work_order_updates"

    id = Column(Integer, primary_key=True, index=True)

    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What happened
    from_status = Column(SqlEnum(WorkOrderStatus), nullable=True)
    to_status = Column(SqlEnum(WorkOrderStatus), nullable=True)
    message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    work_order = relationship("WorkOrder", back_populates="updates")

    def __repr__(self):
        return f"<WorkOrderUpdate wo={self.work_order_id} by={self.user_id}>"