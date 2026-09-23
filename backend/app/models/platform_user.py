# ============================================================
# models/platform_user.py
# ------------------------------------------------------------
# Internal platform identity domain.
#
# Customer users live in app.models.user.User and always belong to an
# organization. Internal staff live here and NEVER carry an
# organization_id. Customer and platform identities must not mix.
# ============================================================

import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum as SqlEnum, Integer, String

from app.core.database import Base


class PlatformUserRole(str, enum.Enum):
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_SALES = "platform_sales"
    PLATFORM_BILLING = "platform_billing"
    PLATFORM_TECH = "platform_tech"
    PLATFORM_SUPPORT = "platform_support"
    PLATFORM_DEV = "platform_dev"


class PlatformUser(Base):
    __tablename__ = "platform_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(
        SqlEnum(
            PlatformUserRole,
            name="platform_user_role",
            native_enum=False,
            length=32,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        role_value = self.role.value if hasattr(self.role, "value") else self.role
        return f"<PlatformUser {self.email} ({role_value})>"
