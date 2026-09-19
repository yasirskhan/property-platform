# ============================================================
# auth.py
# ------------------------------------------------------------
# The "brain" of authentication:
#
#   1. Create a new user (signup)
#      - check email isn't taken
#      - hash the password
#      - save to database
#
#   2. Authenticate a user (login)
#      - find by email
#      - verify password
#
# This file does NOT handle HTTP. It's pure logic.
# Routes will call these functions.
# ============================================================

from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


# ------------------------------------------------------------
# USER LOOKUPS
# ------------------------------------------------------------
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Find a user by email. Returns None if not found."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Find a user by ID. Returns None if not found."""
    return db.query(User).filter(User.id == user_id).first()


# ------------------------------------------------------------
# SIGNUP — create a new user
# ------------------------------------------------------------
def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Create a new user in the database.
    Raises ValueError if the email is already taken.
    """
    # 1. Check if email already exists
    existing = get_user_by_email(db, user_data.email)
    if existing:
        raise ValueError("Email already registered")

    # 2. Hash the password
    hashed = hash_password(user_data.password)

    # 3. Create the User object
    new_user = User(
        email=user_data.email,
        hashed_password=hashed,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        role=user_data.role,
        organization_id=user_data.organization_id,
        is_active=True,
        is_verified=False,
    )

    # 4. Save to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # reload so we get the auto-generated ID

    return new_user


# ------------------------------------------------------------
# LOGIN — verify credentials
# ------------------------------------------------------------
def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Verify email + password.
    Returns the User if correct, or None if not.
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user