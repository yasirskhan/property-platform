"""Tenantless preventive-maintenance schedules and durable occurrences."""
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
from app.core.database import Base

class PreventiveMaintenanceSchedule(Base):
    __tablename__ = "preventive_maintenance_schedules"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=False)
    interval_days = Column(Integer, nullable=False)
    next_due_date = Column(Date, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_preventive_schedules_org_due", "organization_id", "active", "next_due_date"),)

class PreventiveMaintenanceOccurrence(Base):
    __tablename__ = "preventive_maintenance_occurrences"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("preventive_maintenance_schedules.id"), nullable=False)
    due_date = Column(Date, nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("schedule_id", "due_date", name="uq_preventive_schedule_occurrence"),)
