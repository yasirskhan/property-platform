# ============================================================
# models/screening.py
# ------------------------------------------------------------
# Tenant screening provider catalog and per-org settings.
# ============================================================

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Numeric,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ScreeningProvider(Base):
    """Global catalog of screening providers (admin-seeded)."""
    __tablename__ = "screening_providers"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    pricing_info = Column(String(255), nullable=True)
    api_docs_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ScreeningProvider {self.slug}>"


class OrganizationScreeningSettings(Base):
    """Per-organization screening config."""
    __tablename__ = "organization_screening_settings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    provider_slug = Column(String(50), nullable=True)
    is_enabled = Column(Boolean, default=False)

    # Encrypted API credentials
    api_key_encrypted = Column(Text, nullable=True)
    api_secret_encrypted = Column(Text, nullable=True)
    account_id = Column(String(255), nullable=True)

    # Fee
    application_fee = Column(Numeric(10, 2), nullable=True, default=0)
    fee_waived_for_managers = Column(Boolean, default=False)

    # Auto-behavior
    auto_screen_on_apply = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OrgScreeningSettings org={self.organization_id}>"