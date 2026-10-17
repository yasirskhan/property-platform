from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserTwoFactorSettings(Base):
    __tablename__ = "user_two_factor_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    secret_ciphertext = Column(Text, nullable=False)
    recovery_code_hashes = Column(JSON, nullable=False, default=list)
    is_enabled = Column(Boolean, nullable=False, default=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_user_two_factor_org_user"),
    )
