"""Scoped work items for active HOA staff cases."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from app.core.database import Base

class HOACaseTask(Base):
    __tablename__ = "hoa_case_tasks"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False)
    request_key = Column(String(64), nullable=False)
    title = Column(String(160), nullable=False)
    details = Column(Text)
    kind = Column(String(24), nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_on = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="OPEN")
    version = Column(Integer, nullable=False, default=1)
    completed_at = Column(DateTime)
    result_note = Column(String(600))
    created_by_id = Column(Integer, ForeignKey("users.id"))
    updated_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "request_key", name="uq_hoa_case_task_request"),
        Index("ix_hoa_case_task_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
