# ============================================================
# models/audit_log.py
# ------------------------------------------------------------
# Tracks every change to every record.
# Never deleted — permanent history of the platform.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Import User so SQLAlchemy can resolve the relationship
from app.models.user import User  # noqa: F401


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)

    # Who made the change
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)

    # What changed
    entity_type = Column(String(50), nullable=False, index=True)  # property, unit, lease, etc.
    entity_id = Column(Integer, nullable=False, index=True)

    # What happened
    action = Column(String(50), nullable=False)  # created, updated, deleted, restored, status_changed
    field_name = Column(String(100), nullable=True)
    old_value = Column(Text, nullable=True)  # JSON string
    new_value = Column(Text, nullable=True)  # JSON string

    # Where from
    ip_address = Column(String(45), nullable=True)

    # When
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship
    user = relationship("User")

    def __repr__(self):
        return f"<AuditLog {self.entity_type}#{self.entity_id} {self.action}>"