"""Private evidence references scoped to an active HOA staff violation case."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOAViolationEvidence(Base):
    __tablename__ = "hoa_violation_evidence"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_type = Column(String(16), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archived_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("case_id", "attachment_id", name="uq_hoa_violation_evidence_case_attachment"),
        Index("ix_hoa_violation_evidence_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
