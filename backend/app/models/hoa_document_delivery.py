"""Scoped immutable requests and retry state for email delivery of HOA files."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOADocumentDelivery(Base):
    __tablename__ = "hoa_document_deliveries"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    evidence_id = Column(Integer, ForeignKey("hoa_governing_evidence.id"), nullable=False)
    attachment_id = Column(Integer, ForeignKey("entity_attachments.id"), nullable=False)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    request_key = Column(String(64), nullable=False)
    file_sha256 = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="PENDING")
    attempt_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime)
    accepted_at = Column(DateTime)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("association_id", "property_id", "request_key", name="uq_hoa_doc_delivery_request"),
        Index("ix_hoa_doc_delivery_scope", "organization_id", "association_id", "property_id"),
    )
