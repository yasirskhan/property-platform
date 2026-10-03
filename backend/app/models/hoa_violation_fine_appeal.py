"""Immutable association fine appeal records, with no automatic financial posting."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.core.database import Base

class HOAFineAppeal(Base):
    __tablename__ = "hoa_violation_fine_appeals"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False)
    fine_id = Column(Integer, ForeignKey("hoa_violation_fines.id"), nullable=False)
    member_user_id = Column(Integer, ForeignKey("users.id"))
    request_key = Column(String(64), nullable=False)
    received_on = Column(Date, nullable=False)
    appeal_reason = Column(Text, nullable=False)
    supporting_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"))
    received_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(24), nullable=False, default="OPEN", server_default="OPEN")
    decided_on = Column(Date)
    decision_note = Column(Text)
    decided_by_id = Column(Integer, ForeignKey("users.id"))
    decision_board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"))
    decision_request_key = Column(String(64))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    decided_at = Column(DateTime)
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_hoa_fine_appeal_request"),
        UniqueConstraint("organization_id", "decision_request_key", name="uq_hoa_fine_appeal_decision_request"),
    )
