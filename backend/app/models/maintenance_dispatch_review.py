"""Durable staff-only maintenance dispatch review cases.

The unique nullable open_work_order_id makes one OPEN case per work order
a database invariant, even with competing operators. Closing preserves
the case and append-only audit, never messages a crew or vendor.
"""
from datetime import datetime
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class MaintenanceDispatchReview(Base):
    __tablename__ = "maintenance_dispatch_reviews"
    __table_args__ = (
        UniqueConstraint("open_work_order_id", name="uq_maintenance_dispatch_review_open"),
        CheckConstraint("status IN ('open','closed')", name="ck_maintenance_dispatch_review_status"),
        CheckConstraint(
            "(status = 'open' AND open_work_order_id IS NOT NULL AND closed_at IS NULL)"
            " OR (status = 'closed' AND open_work_order_id IS NULL AND closed_at IS NOT NULL)",
            name="ck_maintenance_dispatch_review_lifecycle",
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    open_work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=True)
    status = Column(String(12), nullable=False, default="open")
    reason = Column(Text, nullable=False)
    opened_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
