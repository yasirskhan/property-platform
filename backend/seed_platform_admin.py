"""Seed the first internal platform administrator.

There is intentionally no public/self-signup path for platform staff.
Run this only against a prepared database and only with explicit
environment variables.
"""

from __future__ import annotations

import os

from email_validator import EmailNotValidError, validate_email

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.platform_user import PlatformUser, PlatformUserRole


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def seed() -> None:
    if os.environ.get("PLATFORM_ADMIN_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError(
            "Refusing platform admin seed. Set PLATFORM_ADMIN_SEED_ALLOWED=true "
            "only for an intentional first-admin bootstrap."
        )

    raw_email = _required_env("PLATFORM_ADMIN_EMAIL")
    password = _required_env("PLATFORM_ADMIN_PASSWORD")
    first_name = _required_env("PLATFORM_ADMIN_FIRST_NAME")
    last_name = _required_env("PLATFORM_ADMIN_LAST_NAME")

    if len(password) < 12:
        raise RuntimeError("PLATFORM_ADMIN_PASSWORD must be at least 12 characters")

    try:
        email = validate_email(raw_email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise RuntimeError("PLATFORM_ADMIN_EMAIL is not a valid email address") from exc

    db = SessionLocal()
    try:
        if db.query(PlatformUser).first() is not None:
            raise RuntimeError(
                "Refusing platform admin seed: platform_users already contains an account"
            )

        user = PlatformUser(
            email=email.lower(),
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=PlatformUserRole.PLATFORM_ADMIN,
            is_active=True,
        )
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(user)
        print(f"Seeded first platform admin id={user.id} email={user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
