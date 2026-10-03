from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Index
from app.core.database import Base


class HOAViolationCaseEvent(Base):
    __tablename__ = "hoa_violation_case_events"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage = Column(String(32), nullable=True)
    to_stage = Column(String(32), nullable=False)
    policy_revision = Column(Integer, nullable=True)
    staff_action_on = Column(Date, nullable=True)
    tentative_cure_on = Column(Date, nullable=True)
    tentative_hearing_on = Column(Date, nullable=True)
    proposed_fine = Column(Numeric(14, 2), nullable=True)
    staff_resolution = Column(Text, nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_hoa_violation_event_scope", "organization_id", "association_id", "property_id", "case_id", "id"),)
