"""Org-scoped universal tag vocabulary and scoped, explicit entity assignments."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.core.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    normalized_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", name="uq_tag_org_normalized_name"),
    )


class EntityTag(Base):
    __tablename__ = "entity_tags"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "tag_id", "entity_type", "entity_id", name="uq_entity_tag_scope"),
        Index("ix_entity_tags_target", "organization_id", "entity_type", "entity_id"),
    )
