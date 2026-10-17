"""A violation case's staff-selected potential recipient, not legal debtor status."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Index, UniqueConstraint
from app.core.database import Base


class HOAViolationRecipientDraft(Base):
    __tablename__ = "hoa_violation_recipient_drafts"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False)
    matched_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_hoa_violation_recipient_scope", "organization_id", "association_id", "property_id"),
    )
