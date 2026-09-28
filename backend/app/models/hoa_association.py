"""Staff-recorded HOA associations and explicit multi-property membership, no assessments."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOAAssociation(Base):
    __tablename__ = "hoa_associations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    name_key = Column(String(160), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "name_key", name="uq_hoa_assoc_org_name"),)


class HOAPropertyMembership(Base):
    __tablename__ = "hoa_property_memberships"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("association_id", "property_id", name="uq_hoa_membership_assoc_property"),
        Index("ix_hoa_member_org_assoc", "organization_id", "association_id"),
    )
