"""Explicit organization-owned property groups and memberships."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class PropertyGroup(Base):
    __tablename__ = "property_groups"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    name_key = Column(String(100), nullable=False)  # normalized uniqueness, no cross-org collisions
    description = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "name_key", name="uq_property_group_org_name"),
    )


class PropertyGroupMembership(Base):
    __tablename__ = "property_group_memberships"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("property_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("group_id", "property_id", name="uq_property_group_member"),
        Index("ix_pg_membership_org_group", "organization_id", "group_id"),
    )
