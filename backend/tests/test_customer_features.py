from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.billing import Module, ModuleFeature
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.user import Organization, User, UserRole
from app.routers.features import (
    get_feature_settings,
    get_my_features,
    update_feature_setting,
)
from app.schemas.features import FeatureSettingUpdateIn
from app.services.menu_resolver import resolve_menu_for_user


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _user(db, *, slug: str, role: UserRole = UserRole.ADMIN):
    org = Organization(name=slug.title(), slug=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}-{role.value.lower()}@example.com",
        hashed_password="unused",
        first_name=role.value.title(),
        last_name="User",
        role=role,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return org, user


def _open(db, *keys: str) -> None:
    db.add_all(
        [ReleaseGate(key=key, stage=ReleaseStage.ALL_ORGS) for key in keys]
    )
    db.commit()


def test_customer_flags_hide_unreleased_and_apply_org_configuration() -> None:
    db, engine = _session()
    try:
        org, admin = _user(db, slug="feature-org")
        _open(db, "release.settings.features", "release.properties.map")
        db.add(
            ReleaseGate(
                key="release.accounting.bank_feed",
                stage=ReleaseStage.HIDDEN,
            )
        )
        db.commit()

        result = get_my_features(db=db, current_user=admin)
        assert result.flags["release.properties.map"] is True
        assert "release.accounting.bank_feed" not in result.flags

        settings = get_feature_settings(db=db, current_user=admin)
        assert any(item.key == "release.properties.map" for item in settings.items)

        updated = update_feature_setting(
            "release.properties.map",
            FeatureSettingUpdateIn(enabled=False),
            db=db,
            current_user=admin,
        )
        assert updated.enabled is False
        assert updated.org_config_allowed is False
        assert updated.allowed is False

        refreshed = get_my_features(db=db, current_user=admin)
        assert refreshed.flags["release.properties.map"] is False

        stored = db.query(OrganizationFeatureSetting).one()
        assert stored.organization_id == org.id
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "organization_feature_setting")
            .one()
        )
        assert audit.user_id == admin.id
        assert audit.organization_id == org.id
    finally:
        db.close()
        engine.dispose()


def test_customer_flag_respects_paid_entitlement_without_changing_release_state() -> None:
    db, engine = _session()
    try:
        _, admin = _user(db, slug="paid-feature")
        module = Module(key="bank-feeds", name="Bank Feeds", is_core=False)
        db.add(module)
        db.flush()
        db.add(ModuleFeature(module_id=module.id, feature_key="bank_feeds"))
        _open(db, "release.settings.features", "release.accounting.bank_feed")

        result = get_my_features(db=db, current_user=admin)
        decision = next(
            item
            for item in result.features
            if item.key == "release.accounting.bank_feed"
        )
        assert decision.release_allowed is True
        assert decision.entitlement_allowed is False
        assert decision.allowed is False
    finally:
        db.close()
        engine.dispose()


def test_feature_settings_are_admin_owner_only_and_org_scoped() -> None:
    db, engine = _session()
    try:
        org_a, admin_a = _user(db, slug="org-a")
        org_b, admin_b = _user(db, slug="org-b")
        _, manager = _user(db, slug="org-c", role=UserRole.MANAGER)
        _open(db, "release.settings.features", "release.properties.map")

        update_feature_setting(
            "release.properties.map",
            FeatureSettingUpdateIn(enabled=False),
            db=db,
            current_user=admin_a,
        )
        assert get_my_features(db=db, current_user=admin_a).flags[
            "release.properties.map"
        ] is False
        assert get_my_features(db=db, current_user=admin_b).flags[
            "release.properties.map"
        ] is True
        assert org_a.id != org_b.id

        with pytest.raises(HTTPException) as exc:
            get_feature_settings(db=db, current_user=manager)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_settings_features_menu_consumes_release_gate() -> None:
    db, engine = _session()
    try:
        _, admin = _user(db, slug="menu-feature")
        db.commit()
        keys = {item["key"] for item in resolve_menu_for_user(db, admin)}
        assert "SETTINGS.FEATURES" not in keys

        _open(db, "release.settings.features")
        keys = {item["key"] for item in resolve_menu_for_user(db, admin)}
        assert "SETTINGS.FEATURES" in keys
    finally:
        db.close()
        engine.dispose()


def test_features_control_surface_cannot_disable_itself() -> None:
    db, engine = _session()
    try:
        _, admin = _user(db, slug="self-lockout")
        _open(db, "release.settings.features")
        with pytest.raises(HTTPException) as exc:
            update_feature_setting(
                "release.settings.features",
                FeatureSettingUpdateIn(enabled=False),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 400
    finally:
        db.close()
        engine.dispose()
