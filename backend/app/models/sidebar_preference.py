# ============================================================
# sidebar_preference.py (model)
# ------------------------------------------------------------
# Per-USER sidebar layout.
#
# One row per user. Absence of a row means "use defaults"
# (canonical MENU_KEYS order, nothing hidden).
#
#   order:  list of menu keys in the user's preferred order
#   hidden: list of menu keys the user personally hid
#
# user_id is NOT NULL and UNIQUE. organization_id is stored for
# scoping/filters but is not the key.
#
# See PROJECT_MASTER.md Sections 9 and 42.
# ============================================================

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    JSON,
    DateTime,
    Index,
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

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order = Column(JSON, nullable=False, default=list)
    hidden = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship("Organization")
    user = relationship("User")

    __table_args__ = (
        Index(
            "uq_sidebar_preferences_user_id",
            "user_id",
            unique=True,
        ),
    )