# ============================================================
# models/platform_settings.py
# ------------------------------------------------------------
# Platform-wide settings — one row per key.
# Used for OCR configuration and future integrations.
# ============================================================

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text

from app.core.database import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PlatformSetting {self.key}>"