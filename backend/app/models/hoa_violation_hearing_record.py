"""Immutable association hearing outcome tied to actual notice service and procedure."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base

class HOAViolationHearingRecord(Base):
    __tablename__ = "hoa_violation_hearing_records"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False, unique=True)
    service_record_id = Column(Integer, ForeignKey("hoa_violation_service_records.id"), nullable=False)
    policy_revision = Column(Integer, nullable=False)
    member_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    disposition = Column(String(32), nullable=False)
    held_on = Column(Date)
    record_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"))
    request_key = Column(String(64), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_hoa_hearing_request"),
        Index("ix_hoa_hearing_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
