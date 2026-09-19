# ============================================================
# models/org_email.py
# ------------------------------------------------------------
# Per-organization email (SMTP) settings.
# One row per organization that has custom email configured.
# SMTP password is stored encrypted.
# ============================================================

from datetime import datetime

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

# IMPORTANT: Import Organization so SQLAlchemy can resolve the relationship below.
from app.models.user import Organization  # noqa: F401


class OrganizationEmailSettings(Base):
    __tablename__ = "organization_email_settings"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=False, default="")
    reply_to_email = Column(String(255), nullable=True)

    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_user = Column(String(255), nullable=False)
    smtp_password_encrypted = Column(String(1024), nullable=False)
    smtp_use_tls = Column(Boolean, nullable=False, default=True)

    is_enabled = Column(Boolean, default=True)

    last_test_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")

    def __repr__(self):
        return f"<OrganizationEmailSettings org={self.organization_id} host={self.smtp_host}>"