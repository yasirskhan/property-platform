from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.my_settings as my_settings_router
import app.routers.users as users_router
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.user import Organization, User, UserRole
from app.models.user_personal_settings import UserPersonalSettings
from app.schemas.user import UserUpdate
from app.schemas.user_personal_settings import MySettingsUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="My Settings Org", slug="my-settings-org")
    db.add(org)
    db.flush()
    user = User(
        email="my-settings@example.com",
        hashed_password="x",
        first_name="My",
        last_name="Settings",
        role=UserRole.MANAGER,
        organization_id=org.id,
        is_active=True,
    )
    other = User(
        email="other-settings@example.com",
        hashed_password="x",
        first_name="Other",
        last_name="User",
        role=UserRole.TENANT,
        organization_id=org.id,
        is_active=True,
    )
    db.add_all([user, other])
    db.commit()
    return org, user, other


def test_my_settings_defaults_update_and_user_isolation():
    db, engine = _session()
    try:
        org, user, other = _seed(db)

        initial = my_settings_router.get_my_settings(db=db, current_user=user)
        assert initial.user_id == user.id
        assert initial.organization_id == org.id
        assert initial.email_notifications_enabled is True
        assert initial.email_signature is None
        assert initial.reply_to_email is None
        assert initial.language_override is None
        assert initial.export_format_override is None
        assert db.query(UserPersonalSettings).count() == 0

        updated = my_settings_router.update_my_settings(
            MySettingsUpdate(
                email_notifications_enabled=False,
                email_signature="Regards,\nMy Settings",
                reply_to_email="reply@example.com",
                language_override="en-US",
                export_format_override="excel",
            ),
            db=db,
            current_user=user,
        )
        assert updated.email_notifications_enabled is False
        assert updated.email_signature == "Regards,\nMy Settings"
        assert str(updated.reply_to_email) == "reply@example.com"
        assert updated.language_override == "en-US"
        assert updated.export_format_override == "EXCEL"

        other_view = my_settings_router.get_my_settings(db=db, current_user=other)
        assert other_view.user_id == other.id
        assert other_view.email_notifications_enabled is True
        assert other_view.email_signature is None

        row = db.query(UserPersonalSettings).filter_by(user_id=user.id).one()
        assert row.organization_id == org.id
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "user_personal_settings",
            AuditLog.entity_id == user.id,
            AuditLog.action == "updated",
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_user_can_update_own_profile_photo():
    db, engine = _session()
    try:
        _, user, _ = _seed(db)
        result = users_router.update_user(
            user.id,
            UserUpdate(profile_photo_url="/uploads/avatar.webp"),
            db=db,
            current_user=user,
        )
        assert result.profile_photo_url == "/uploads/avatar.webp"
    finally:
        db.close()
        engine.dispose()


def test_my_settings_validates_personal_overrides():
    with pytest.raises(ValidationError):
        MySettingsUpdate(export_format_override="PDF")
    with pytest.raises(ValidationError):
        MySettingsUpdate(language_override="not a language code")
