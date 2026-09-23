"""Seed the deterministic account used by browser smoke tests."""
from __future__ import annotations

import os

from app.core.auth import create_user
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

E2E_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
E2E_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
E2E_ORG = os.environ.get("E2E_ORG_NAME", "E2E Test Organization")


def seed() -> None:
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError(
            "Refusing E2E seed. Set E2E_SEED_ALLOWED=true only for a disposable test database."
        )

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == E2E_EMAIL).first()
        if existing:
            raise RuntimeError(f"E2E account already exists: {E2E_EMAIL}")

        user = create_user(
            db,
            UserCreate(
                email=E2E_EMAIL,
                password=E2E_PASSWORD,
                first_name="E2E",
                last_name="Admin",
                role=UserRole.ADMIN,
                organization_name=E2E_ORG,
            ),
        )
        print(f"Seeded E2E admin id={user.id} org={user.organization_id}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
