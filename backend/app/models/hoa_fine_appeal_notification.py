"""Scoped, immutable HOA appeal outcome email outbox, not proof of service."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class HOAFineAppealNotification(Base):
    __tablename__ = "hoa_fine_appeal_notifications"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False)
    fine_id = Column(Integer, ForeignKey("hoa_violation_fines.id"), nullable=False)
    appeal_id = Column(Integer, ForeignKey("hoa_violation_fine_appeals.id"), nullable=False, unique=True)
    template_id = Column(Integer, ForeignKey("letter_templates.id"), nullable=False)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_key = Column(String(64), nullable=False)
    subject_snapshot = Column(String(180), nullable=False)
    body_snapshot = Column(Text, nullable=False)
    outcome_snapshot = Column(String(16), nullable=False)
    status = Column(String(24), nullable=False, default="PENDING", server_default="PENDING")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at = Column(DateTime)
    smtp_accepted_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_hoa_appeal_notification_request"),
        Index("ix_hoa_appeal_notification_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
