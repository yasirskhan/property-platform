from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import create_user
from app.core.database import Base
from app.models.user import (
    SELF_SERVE_PENDING_BILLING_STATE,
    Organization,
    UserRole,
)
from app.schemas.user import UserCreate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.OWNER])
def test_self_serve_buyer_signup_starts_pending_billing(
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole,
) -> None:
    db, engine = _session()
    monkeypatch.setattr("app.core.auth.hash_password", lambda _password: "hashed")
    try:
        user = create_user(
            db,
            UserCreate(
                email=f"{role.value.lower()}-signup@example.com",
                password="password123",
                first_name="Self",
                last_name="Serve",
                role=role,
                organization_name=f"{role.value.title()} Billing Org",
            ),
        )

        org = db.get(Organization, user.organization_id)
        assert org is not None
        assert org.state == SELF_SERVE_PENDING_BILLING_STATE
        assert org.is_active is True
    finally:
        db.close()
        engine.dispose()


def test_invited_user_does_not_change_existing_organization_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    monkeypatch.setattr("app.core.auth.hash_password", lambda _password: "hashed")
    try:
        org = Organization(
            name="Existing Org",
            slug="existing-org",
            state="ACTIVE",
            is_active=True,
        )
        db.add(org)
        db.commit()

        user = create_user(
            db,
            UserCreate(
                email="manager-invite@example.com",
                password="password123",
                first_name="Invited",
                last_name="Manager",
                role=UserRole.MANAGER,
                organization_id=org.id,
            ),
        )

        db.refresh(org)
        assert user.organization_id == org.id
        assert org.state == "ACTIVE"
    finally:
        db.close()
        engine.dispose()
