# ============================================================
# user_permission.py
# ------------------------------------------------------------
# Layer 3 of the menu permission system.
#
# Per-user overrides of the role default.
#
# Only rows that represent an ACTUAL override exist here. If a
# user has no row for a menu_key, the role default from
# menu_permissions applies. Presence of a row means:
#   visible = False -> force-hide this item for this user
#   visible = True  -> force-allow this item for this user IF the
#                      role already allowed it (True cannot grant
#                      what the role denied)
#
# set_by_user_id records who made the change (audit trail).
# ============================================================

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserPermission(Base):
    __tablename__ = "user_permissions"

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

    menu_key = Column(String(64), nullable=False, index=True)

    visible = Column(Boolean, nullable=False)

    # Who set this override. Nullable so deleting a manager doesn't
    # cascade-delete their historic permission changes.
    set_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship("Organization")
    user = relationship("User", foreign_keys=[user_id])
    set_by = relationship("User", foreign_keys=[set_by_user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "menu_key", name="uq_user_permissions_user_key"),
        Index("ix_user_permissions_user", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserPermission user={self.user_id} "
            f"key={self.menu_key} visible={self.visible}>"
        )