"""Encrypted address and employment details; never in legacy application SSN fields."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from app.core.database import Base


class ApplicationPrivateDetails(Base):
    __tablename__ = "application_private_details"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("lease_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_payload = Column(Text, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("application_id", name="uq_application_private_app"),
        Index("ix_application_private_scope", "organization_id", "application_id"),
    )
