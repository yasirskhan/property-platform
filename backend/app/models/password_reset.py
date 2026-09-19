# ============================================================
# models/password_reset.py
# ------------------------------------------------------------
# Stores password reset tokens.
# Each token is single-use and expires after 1 hour.
# ============================================================

from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# IMPORTANT: Import User so SQLAlchemy can resolve the relationship below.
from app.models.user import User  # noqa: F401


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    token = Column(String(255), unique=True, index=True, nullable=False)

    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User")

    @staticmethod
    def default_expiry() -> datetime:
        return datetime.utcnow() + timedelta(hours=1)

    def is_valid(self) -> bool:
        return (not self.used) and self.expires_at > datetime.utcnow()

    def __repr__(self):
        return f"<PasswordResetToken user={self.user_id} used={self.used}>"