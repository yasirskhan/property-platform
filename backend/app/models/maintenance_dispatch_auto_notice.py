"""Durable, system-authored in-app dispatch escalation attention evidence.

One notice per unique work-order crew-offer timestamp; it never implies
external delivery, vendor acceptance, an automatic assignment or approval.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from app.core.database import Base


class MaintenanceDispatchAutoNotice(Base):
    __tablename__ = "maintenance_dispatch_auto_notices"
    __table_args__ = (
        UniqueConstraint("work_order_id", "assigned_at", name="uq_dispatch_auto_notice_assignment"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    crew_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    group_id = Column(Integer, ForeignKey("maintenance_dispatch_groups.id", ondelete="RESTRICT"), nullable=False)
    assigned_at = Column(DateTime, nullable=False)
    timeout_minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
