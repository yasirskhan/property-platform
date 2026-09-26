"""Per-user personal settings that are independent of organization settings."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserPersonalSettings(Base):
    __tablename__ = "user_personal_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_notifications_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    email_signature = Column(Text, nullable=True)
    reply_to_email = Column(String(255), nullable=True)
    language_override = Column(String(16), nullable=True)
    export_format_override = Column(String(10), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User")
    organization = relationship("Organization")
