# ============================================================
# user.py
# ------------------------------------------------------------
# This file defines our database tables for users and
# organizations (a property owner company = one organization).
#
# Every person who logs in — admin, owner, manager, crew,
# tenant — is stored in the SAME users table, distinguished
# by their "role" column.
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
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ------------------------------------------------------------
# ROLES
# ------------------------------------------------------------
# This is the list of roles in the system.
# The order roughly matches the hierarchy you described.
# ------------------------------------------------------------
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OWNER = "owner"
    MANAGER = "manager"
    CREW = "crew"
    TENANT = "tenant"
    APPLICANT = "applicant"


# ------------------------------------------------------------
# ORGANIZATION
# ------------------------------------------------------------
# Each property owner company is an "Organization".
# This is what keeps data separated between different owners.
# ------------------------------------------------------------
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (who belongs to this organization)
    users = relationship("User", back_populates="organization")


# ------------------------------------------------------------
# USER
# ------------------------------------------------------------
# Every person who logs in. The "role" column decides what
# they can see and do.
# ------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # --- Login fields ---
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # --- Personal info ---
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=True)
    profile_photo_url = Column(String(500), nullable=True)

    # --- Role and organization ---
    role = Column(SqlEnum(UserRole), nullable=False, default=UserRole.TENANT)

    # Admin is NOT tied to any single organization (they oversee all).
    # Everyone else (owner, manager, crew, tenant) belongs to one org.
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=True,  # nullable so admin can exist without an org
        index=True,
    )

    # --- Status ---
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # --- Timestamps ---
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Relationships ---
    organization = relationship("Organization", back_populates="users")

    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"