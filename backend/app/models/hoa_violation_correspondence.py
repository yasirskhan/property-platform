"""Immutable internal HOA correspondence drafts, never statutory notices."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class HOAViolationCorrespondenceDraft(Base):
    __tablename__ = "hoa_violation_correspondence_drafts"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    policy_id = Column(Integer, ForeignKey("hoa_procedure_policies.id", ondelete="RESTRICT"), nullable=False)
    policy_revision = Column(Integer, nullable=False)
    recipient_reference_id = Column(Integer, ForeignKey("hoa_violation_recipient_drafts.id", ondelete="RESTRICT"), nullable=False)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False)
    matched_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    stage = Column(String(32), nullable=False)
    draft_notice_on = Column(Date, nullable=True)
    tentative_cure_on = Column(Date, nullable=True)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    prepared_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    prepared_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "revision", name="uq_hoa_violation_draft_case_revision"),
        Index("ix_hoa_violation_draft_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
