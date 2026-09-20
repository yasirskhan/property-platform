# ============================================================
# sidebar_preference.py
# ------------------------------------------------------------
# Per-USER sidebar layout.
#
# Was per-organization before the menu-permissions migration;
# now one row per user (user_id is unique where not null).
#
#   order:  list of menu keys in the user's preferred order
#   hidden: list of menu keys the user personally hid
#
# The row is created on first save. Absence of a row means
# "use defaults" (canonical MENU_KEYS order, nothing hidden).
# ============================================================

from sqlalchemy import (
    Column, Integer, ForeignKey, JSON, DateTime, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class SidebarPreference(Base):
    __tablename__ = "sidebar_preferences"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nullable because the migration had to backfill legacy rows and
    # because a user might exist without a saved preference yet.
    # Unique when present (enforced by partial unique index at DB level).
    user_id = Column(Integer, nullable=True, index=True)

    order = Column(JSON, nullable=False, default=list)
    hidden = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship("Organization")

    __table_args__ = (
        Index(
            "uq_sidebar_preferences_user_id",
            "user_id",
            unique=True,
            sqlite_where=None,
        ),
    )