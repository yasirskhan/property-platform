# ============================================================
# currency.py
# ------------------------------------------------------------
# Per-org currency list.
#
# Each org starts with 9 system currencies (seeded by migration
# 8e1243432666). Admins/Owners can add custom ones on top.
#
# is_system = True  -> seeded default, cannot be deleted
# is_system = False -> customer-added, can be deleted
#
# No conversion. The org's ACTIVE currency is stored on
# organizations.currency (one code). This table defines what's
# selectable in the dropdown.
#
# See PROJECT_MASTER.md Section 68.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_currency_org_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    code = Column(String(3), nullable=False)          # e.g. "USD", "PKR"
    name = Column(String(100), nullable=False)        # e.g. "Pakistani Rupee"
    symbol = Column(String(10), nullable=False)       # e.g. "$", "\u20b9"
    locale = Column(String(20), nullable=False)       # e.g. "en-PK"
    decimal_places = Column(Integer, nullable=False, default=2)

    is_system = Column(Boolean, nullable=False, default=False)   # seeded default
    is_active = Column(Boolean, nullable=False, default=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")