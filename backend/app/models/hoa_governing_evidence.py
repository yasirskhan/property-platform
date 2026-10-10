"""Association/property-scoped pointers to existing PRIVATE property attachments.
Staff evidence only: neither legal validity nor a governance decision.
"""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOAGoverningEvidence(Base):
    __tablename__ = "hoa_governing_evidence"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_type = Column(String(32), nullable=False)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    supersedes_id = Column(Integer, ForeignKey("hoa_governing_evidence.id", ondelete="RESTRICT"))
    replacement_request_key = Column(String(64))
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("association_id", "property_id", "attachment_id", name="uq_hoa_evidence_attach"),
        Index("ix_hoa_evidence_scope", "organization_id", "association_id", "property_id"),
        UniqueConstraint("organization_id", "replacement_request_key", name="uq_hoa_evidence_replacement_request"),
        UniqueConstraint("supersedes_id", name="uq_hoa_governing_evidence_supersedes_id"),
        CheckConstraint("revision >= 1", name="ck_hoa_evidence_revision_positive"),
    )
