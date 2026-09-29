"""Association-authorized, exact-revision violation correspondence email attempts.

SMTP acceptance is not proof of receipt or statutory notice service.
This row never establishes member liability, a cure deadline or a fine.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOAViolationNoticeDelivery(Base):
    __tablename__ = "hoa_violation_notice_deliveries"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False)
    correspondence_id = Column(Integer, ForeignKey("hoa_violation_correspondence_drafts.id"), nullable=False, unique=True)
    correspondence_revision = Column(Integer, nullable=False)
    policy_id = Column(Integer, ForeignKey("hoa_procedure_policies.id"), nullable=False)
    policy_revision = Column(Integer, nullable=False)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_key = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="PENDING")
    attempt_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime)
    smtp_accepted_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_hoa_violation_delivery_request"),
        Index("ix_hoa_violation_delivery_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
