# ============================================================
# auth.py
# ------------------------------------------------------------
# The "brain" of authentication.
#
#   1. Create a new user (signup)
#      - validate the signup shape
#      - hash the password
#      - create an Organization if needed
#      - seed the org's menu permissions
#      - save the user, atomically
#
#   2. Authenticate a user (login)
#      - find by email
#      - verify password
#
# This file does NOT handle HTTP. It's pure logic.
# ============================================================

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole, Organization
from app.schemas.user import UserCreate
from app.services.menu_seed import seed_menu_permissions_for_org


# ------------------------------------------------------------
# LOOKUPS
# ------------------------------------------------------------
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _slugify(name: str) -> str:
    """Turn 'Yasir Properties LLC' into 'yasir-properties-llc'.

    Lowercase, alphanumeric + hyphens, collapsed runs, trimmed.
    Empty result falls back to 'org'.
    """
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "org"


def _unique_slug(db: Session, base: str) -> str:
    """Ensure the slug is unique. Append -2, -3, ... on collision."""
    if not db.query(Organization).filter(Organization.slug == base).first():
        return base
    n = 2
    while True:
        candidate = f"{base}-{n}"
        if not db.query(Organization).filter(Organization.slug == candidate).first():
            return candidate
        n += 1


def _create_organization(db: Session, name: str) -> Organization:
    """Create a new Organization with a unique slug. No commit."""
    slug = _unique_slug(db, _slugify(name))
    org = Organization(
        name=name.strip(),
        slug=slug,
        is_active=True,
        state="ACTIVE",
    )
    db.add(org)
    db.flush()  # assigns org.id
    return org


# ------------------------------------------------------------
# SIGNUP
# ------------------------------------------------------------
def create_user(db: Session, user_data: UserCreate) -> User:
    """Create a new user.

    Rules:
      * Email must be unique.
      * If `organization_id` is provided -> join that org (invited
        user). The role must NOT be ADMIN in that case (an admin
        joins by creating a new org, not by being invited into one).
      * If `organization_id` is missing:
          - role ADMIN or OWNER -> must supply `organization_name`.
            We create a new organization and link the user to it.
          - any other role -> refuse. There is nowhere to attach them.

    Raises ValueError with a human-readable message on any violation.
    """
    # 1. Email uniqueness
    if get_user_by_email(db, user_data.email):
        raise ValueError("Email already registered")

    # 2. Normalize inputs
    role = user_data.role
    # role may be a UserRole enum or a raw string depending on caller
    role_value = role.value if hasattr(role, "value") else str(role).upper()

    # 3. Resolve or create the organization
    org: Optional[Organization] = None

    if user_data.organization_id is not None:
        # --- Invited user path ---
        if role_value == "ADMIN":
            raise ValueError(
                "An admin cannot join an existing organization. "
                "Sign up without an organization_id and provide "
                "organization_name to create a new one."
            )
        org = (
            db.query(Organization)
            .filter(Organization.id == user_data.organization_id)
            .first()
        )
        if org is None:
            raise ValueError("Organization not found")
        if not org.is_active:
            raise ValueError("Organization is not active")

    else:
        # --- Brand-new company path ---
        if role_value in ("ADMIN", "OWNER"):
            if not user_data.organization_name or not user_data.organization_name.strip():
                raise ValueError(
                    "organization_name is required when signing up "
                    "as an admin or owner."
                )
            org = _create_organization(db, user_data.organization_name)
            # Seed its menu permissions with defaults
            seed_menu_permissions_for_org(db, org.id)
        else:
            # TENANT, CREW, MANAGER, VENDOR, APPLICANT — no self-signup
            raise ValueError(
                "This account type must be invited by an existing "
                "organization. Please contact your administrator."
            )

    # 4. Hash password
    hashed = hash_password(user_data.password)

    # 5. Create the user
    new_user = User(
        email=user_data.email,
        hashed_password=hashed,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        role=role,
        organization_id=org.id if org else None,
        is_active=True,
        is_verified=False,
    )
    db.add(new_user)

    # 6. Commit — either everything or nothing
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(new_user)
    return new_user


# ------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------
def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user