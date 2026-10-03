"""Configurable retention policy per data class."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


ALLOWED_RETENTION_DAYS = {30, 365, 2555}
FOREVER = None


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "data_class",
            name="uq_retention_org_data_class",
        ),
        CheckConstraint(
            "retention_days IS NULL OR retention_days IN (30, 365, 2555)",
            name="ck_retention_supported_window",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    data_class = Column(String(100), nullable=False, index=True)
    retention_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization = relationship("Organization")

    def __repr__(self) -> str:
        window = "forever" if self.retention_days is None else f"{self.retention_days}d"
        return f"<DataRetentionPolicy {self.data_class} {window}>"
