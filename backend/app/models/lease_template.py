"""Three-level lease document drafting: template -> addendum -> universal attachment.

This is NOT an e-signature engine or active lease contract store.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from app.core.database import Base


class LeaseTemplate(Base):
    __tablename__ = "lease_templates"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    # NULL means organization-wide; otherwise scoped to one active property.
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"),
                         nullable=True, index=True)
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    __table_args__ = (Index("ix_lease_templates_scope", "organization_id", "property_id", "is_active"),)


class LeaseTemplateAddendum(Base):
    __tablename__ = "lease_template_addenda"
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("lease_templates.id", ondelete="RESTRICT"),
                         nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    # Copy of immutable parent scope, so generic attachments can scope correctly.
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=True)
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    __table_args__ = (Index("ix_lease_addenda_template", "organization_id", "template_id", "position"),)
