"""Organization-scoped maintenance dispatch groups, exclusive property binding, and policies.

Settings do not dispatch, notify or commit to pay anyone. Every assigned
property resolves to exactly one group: an explicit binding or DEFAULT.
"""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from app.core.database import Base


class MaintenanceDispatchGroup(Base):
    __tablename__ = "maintenance_dispatch_groups"
    __table_args__ = (
        UniqueConstraint("organization_id", "name_key", name="uq_maintenance_group_name"),
        CheckConstraint("business_start_hour BETWEEN 0 AND 23", name="ck_maintenance_start_hour"),
        CheckConstraint("business_end_hour BETWEEN 1 AND 24", name="ck_maintenance_end_hour"),
        CheckConstraint("business_end_hour > business_start_hour", name="ck_maintenance_business_hours"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    name_key = Column(String(100), nullable=False)
    timezone_name = Column(String(64), nullable=False, default="UTC")
    business_start_hour = Column(Integer, nullable=False, default=9)
    business_end_hour = Column(Integer, nullable=False, default=17)
    automation_requested = Column(Boolean, nullable=False, default=False)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaintenanceDispatchProperty(Base):
    """One explicit nondefault override per property; all others inherit DEFAULT."""
    __tablename__ = "maintenance_dispatch_properties"
    __table_args__ = (
        UniqueConstraint("property_id", name="uq_maintenance_dispatch_property"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("maintenance_dispatch_groups.id", ondelete="RESTRICT"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MaintenanceDispatchRule(Base):
    """Configured policy: no messaging or autonomous escalation executor."""
    __tablename__ = "maintenance_dispatch_rules"
    __table_args__ = (
        UniqueConstraint("group_id", "urgency", "daypart", name="uq_maintenance_dispatch_rule"),
        CheckConstraint("urgency IN ('emergency','normal','low')", name="ck_maintenance_dispatch_urgency"),
        CheckConstraint("daypart IN ('business_hours','after_hours')", name="ck_maintenance_dispatch_daypart"),
        CheckConstraint("first_target IN ('crew','vendor','manager')", name="ck_maintenance_dispatch_first_target"),
        CheckConstraint("backup_target IN ('vendor','manager')", name="ck_maintenance_dispatch_backup_target"),
        CheckConstraint("timeout_minutes BETWEEN 1 AND 1440", name="ck_maintenance_dispatch_timeout"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("maintenance_dispatch_groups.id", ondelete="RESTRICT"), nullable=False, index=True)
    urgency = Column(String(16), nullable=False)
    daypart = Column(String(20), nullable=False)
    first_target = Column(String(12), nullable=False, default="crew")
    backup_target = Column(String(12), nullable=False, default="vendor")
    timeout_minutes = Column(Integer, nullable=False, default=15)
    escalate = Column(Boolean, nullable=False, default=False)
    primary_contact_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    backup_contact_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
