"""Universal attachments linked to organization-scoped entities."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from app.core.database import Base


class EntityAttachment(Base):
    __tablename__ = "entity_attachments"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    storage_key = Column(String(255), nullable=False, unique=True, index=True)
    original_name = Column(String(255), nullable=False)
    content_type = Column(String(255), nullable=False, default="application/octet-stream")
    size_bytes = Column(Integer, nullable=False)
    share_with_tenants = Column(Boolean, nullable=False, default=False)
    share_with_owners = Column(Boolean, nullable=False, default=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_entity_attachments_target",
            "organization_id",
            "entity_type",
            "entity_id",
            "is_active",
            "created_at",
        ),
    )
