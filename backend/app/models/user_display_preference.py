# ============================================================
# user_display_preference.py
# ------------------------------------------------------------
# Per-user display settings for the app UI.
#
# One row per user. Created lazily on first GET of
# /api/settings/display, or on signup.
#
# See PROJECT_MASTER.md Section 58.
#
# Fields:
#   layout_mode   TABS | VERTICAL        (default TABS)
#   theme         LIGHT | DARK | AUTO    (default LIGHT)
#   density       COMPACT | COMFORTABLE | SPACIOUS
#   date_format   US | ISO | EU
#   number_format US | EU | SPACE
#   font_size     SMALL | NORMAL | LARGE
#   accent_color  hex string, nullable
#   reduce_motion bool
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


class UserDisplayPreference(Base):
    __tablename__ = "user_display_preferences"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    layout_mode = Column(String(20), nullable=False, default="TABS", server_default="TABS")
    theme = Column(String(20), nullable=False, default="LIGHT", server_default="LIGHT")
    density = Column(String(20), nullable=False, default="COMFORTABLE", server_default="COMFORTABLE")
    date_format = Column(String(20), nullable=False, default="US", server_default="US")
    number_format = Column(String(20), nullable=False, default="US", server_default="US")
    font_size = Column(String(20), nullable=False, default="NORMAL", server_default="NORMAL")
    accent_color = Column(String(20), nullable=True)
    reduce_motion = Column(Boolean, nullable=False, default=False, server_default="0")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")