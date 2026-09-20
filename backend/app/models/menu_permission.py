# ============================================================
# menu_permission.py
# ------------------------------------------------------------
# Layer 2 of the menu permission system.
#
# One row per (organization, role, menu_key).
#   visible = True  -> this role sees this menu item (subject to
#                      Layers 3 and 4 which can still hide it)
#   visible = False -> this role does NOT see this menu item
#
# Rows are seeded on org creation and on migration. The Roles
# tab in Settings -> Permissions edits these rows.
#
# Hard rule: layers 3 and 4 can only SUBTRACT visibility, never
# add. Only Layer 1 (plan) can grant. So a False here is final
# for that role.
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


class MenuPermission(Base):
    __tablename__ = "menu_permissions"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stored uppercase to match users.role values (ADMIN, OWNER, ...).
    role = Column(String(32), nullable=False, index=True)

    # e.g. "ACCOUNTING.RECEIVABLES"
    menu_key = Column(String(64), nullable=False, index=True)

    visible = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "role", "menu_key",
            name="uq_menu_permissions_org_role_key",
        ),
        Index("ix_menu_permissions_org_role", "organization_id", "role"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuPermission org={self.organization_id} "
            f"role={self.role} key={self.menu_key} visible={self.visible}>"
        )