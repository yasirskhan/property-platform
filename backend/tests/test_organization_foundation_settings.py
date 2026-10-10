from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.data_retention_policy import DataRetentionPolicy
from app.models.user import Organization, User, UserRole
from app.routers.organizations import (
    get_foundation_settings,
    update_foundation_settings,
)
from app.schemas.organization_settings import FoundationSettingsUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _user(db, org: Organization, role: UserRole = UserRole.ADMIN) -> User:
    user = User(
        email=f"{role.value.lower()}-{org.id}@example.com",
        hashed_password="not-used",
        first_name="Org",
        last_name="User",
        role=role,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_admin_updates_lock_region_and_retention_with_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org = Organization(name="Settings Org", slug="settings-org")
        db.add(org)
        db.commit()
        admin = _user(db, org)

        monkeypatch.setattr(settings, "PRIMARY_DATA_REGION", "us-east-1")

        result = update_foundation_settings(
            org.id,
            FoundationSettingsUpdate(
                locked_through_date=date(2026, 9, 30),
                data_region="us-east-1",
                retention_policies={"audit": 2555, "temporary_exports": 30},
            ),
            db,
            admin,
        )

        assert result["locked_through_date"] == date(2026, 9, 30)
        assert result["data_region"] == "us-east-1"
        assert result["retention_policies"]["audit"] == 2555
        assert result["retention_policies"]["temporary_exports"] == 30
        assert db.query(DataRetentionPolicy).count() == 2

        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "foundation_settings_updated")
            .one()
        )
        assert audit.user_id == admin.id
        assert audit.organization_id == org.id
    finally:
        db.close()
        engine.dispose()


def test_non_admin_cannot_change_foundation_settings() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Manager Org", slug="manager-org")
        db.add(org)
        db.commit()
        manager = _user(db, org, UserRole.MANAGER)

        with pytest.raises(HTTPException) as exc:
            update_foundation_settings(
                org.id,
                FoundationSettingsUpdate(locked_through_date=date(2026, 9, 30)),
                db,
                manager,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_cross_org_foundation_settings_are_hidden() -> None:
    db, engine = _session()
    try:
        own = Organization(name="Own", slug="own-org")
        other = Organization(name="Other", slug="other-org")
        db.add_all([own, other])
        db.commit()
        admin = _user(db, own)

        with pytest.raises(HTTPException) as exc:
            get_foundation_settings(other.id, db, admin)
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_unconfigured_secondary_region_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org = Organization(name="Region Org", slug="region-org")
        db.add(org)
        db.commit()
        admin = _user(db, org)

        monkeypatch.setattr(settings, "PRIMARY_DATA_REGION", "us-east-1")
        monkeypatch.setattr(settings, "REGIONAL_DATABASE_URLS_JSON", "{}")

        with pytest.raises(HTTPException) as exc:
            update_foundation_settings(
                org.id,
                FoundationSettingsUpdate(data_region="eu-west-1"),
                db,
                admin,
            )
        assert exc.value.status_code == 400
    finally:
        db.close()
        engine.dispose()
