"""Immutable association-reported evidence of notice service, not a legal certification."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base

class HOAViolationServiceRecord(Base):
    __tablename__ = "hoa_violation_service_records"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False, unique=True)
    correspondence_id = Column(Integer, ForeignKey("hoa_violation_correspondence_drafts.id"), nullable=False)
    correspondence_revision = Column(Integer, nullable=False)
    policy_revision = Column(Integer, nullable=False)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"), nullable=False)
    member_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    service_proof_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"), nullable=False)
    delivery_method = Column(String(24), nullable=False)
    served_on = Column(Date, nullable=False)
    cure_earliest_on = Column(Date, nullable=False)
    hearing_request_earliest_on = Column(Date, nullable=False)
    request_key = Column(String(64), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_hoa_service_request"),
        Index("ix_hoa_service_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
