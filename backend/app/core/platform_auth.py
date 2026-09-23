"""Authentication helpers for the internal platform identity domain."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.platform_user import PlatformUser


def get_platform_user_by_email(db: Session, email: str) -> Optional[PlatformUser]:
    return (
        db.query(PlatformUser)
        .filter(PlatformUser.email == email.strip().lower())
        .first()
    )


def get_platform_user_by_id(db: Session, user_id: int) -> Optional[PlatformUser]:
    return db.query(PlatformUser).filter(PlatformUser.id == user_id).first()


def authenticate_platform_user(
    db: Session,
    email: str,
    password: str,
) -> Optional[PlatformUser]:
    user = get_platform_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
