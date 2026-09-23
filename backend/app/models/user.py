# ============================================================
# user.py
# ------------------------------------------------------------
# Database tables for users and organizations.
#
# Every CUSTOMER-SIDE person who logs in (admin, owner, manager,
# crew, tenant, vendor, applicant) lives in the same `users`
# table, distinguished by their role column.
#
# Every one of those users belongs to EXACTLY ONE organization.
# That includes ADMIN — the admin is the boss of THEIR OWN
# customer company, not of the platform.
#
# The PLATFORM side (us: sales, billing, tech, support, dev)
# lives in a completely separate table called `platform_users`,
# which will be built in a later phase. Nothing in this file
# ever touches platform staff.
# ============================================================

import enum
from datetime import date, datetime

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
# ROLES (customer-side)
# ------------------------------------------------------------
# These are the roles a CUSTOMER company can have.
# Values are UPPERCASE because that is what the database has
# always stored and what every other part of the system
# (menu_permissions, resolver, matrix) expects.
# ------------------------------------------------------------
class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    CREW = "CREW"
    TENANT = "TENANT"
    VENDOR = "VENDOR"
    VENDOR_CREW = "VENDOR_CREW"
    APPLICANT = "APPLICANT"


# ------------------------------------------------------------
# ORGANIZATION
# ------------------------------------------------------------
# Each customer company is an "Organization".
# This is what isolates their data from every other customer.
#
# `state` drives the subscription lifecycle. It is not enforced
# anywhere yet — that comes in Phase 10 (Subscription & Billing).
# We add the column now so the schema is ready.
# ------------------------------------------------------------
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)

    # Subscription state placeholder.
    # ACTIVE | PAST_DUE | RESTRICTED | SUSPENDED | CANCELLED
    state = Column(String(20), nullable=False, default="ACTIVE", index=True)

    # Per-org currency. Each customer org operates in exactly
    # one currency. No exchange, no conversion. Column added by
    # migration 8c2e766863c0; see PROJECT_MASTER.md Section 59.
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")

    # Foundation 3.4.5 organization controls.
    # Transactions dated on or before locked_through_date are closed.
    locked_through_date = Column(Date, nullable=True, index=True)

    # Logical residency region. Physical routing remains single-region
    # until another regional database is explicitly configured.
    data_region = Column(
        String(32),
        nullable=False,
        default="us-east-1",
        server_default="us-east-1",
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="organization")


# ------------------------------------------------------------
# USER
# ------------------------------------------------------------
# Every CUSTOMER-side person who logs in.
# The role column decides what they can see and do.
# Every user belongs to exactly one organization.
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

    # Every user belongs to one organization.
    # Nullable at the DB level only because the migration has to
    # tolerate legacy rows; the application enforces NOT NULL for
    # all new signups. The backfill migration fixes the legacy rows.
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=True,
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
        role_value = self.role.value if hasattr(self.role, "value") else self.role
        return f"<User {self.email} ({role_value})>"