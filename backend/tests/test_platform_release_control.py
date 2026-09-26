from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user, platform_login
from app.routers.platform_flags import update_release_gate
from app.schemas.platform_control import PlatformLoginRequest, ReleaseGateUpdateIn
from app.services.release_gate_seed import extract_release_gate_keys, seed_release_gates


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _platform_user(db, role=PlatformUserRole.PLATFORM_ADMIN) -> PlatformUser:
    user = PlatformUser(
        email=f"{role.value}@example.com",
        hashed_password=hash_password("test-platform-password"),
        first_name="Platform",
        last_name="User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_platform_login_issues_platform_token_and_rejects_customer_token() -> None:
    db, engine = _session()
    try:
        user = _platform_user(db)
        token = platform_login(
            PlatformLoginRequest(
                email=user.email,
                password="test-platform-password",
            ),
            db,
        )
        resolved = get_current_platform_user(token=token.access_token, db=db)
        assert resolved.id == user.id

        with pytest.raises(HTTPException) as exc:
            get_current_platform_user(token=create_access_token(user.id), db=db)
        assert exc.value.status_code == 401
    finally:
        db.close()
        engine.dispose()


def test_release_gate_update_is_platform_only_and_audited() -> None:
    db, engine = _session()
    try:
        admin = _platform_user(db)
        org = Organization(name="Beta Org", slug="beta-org")
        gate = ReleaseGate(key="release.example", stage=ReleaseStage.HIDDEN)
        db.add_all([org, gate])
        db.commit()

        result = update_release_gate(
            "release.example",
            ReleaseGateUpdateIn(
                stage=ReleaseStage.BETA,
                organization_ids=[org.id],
            ),
            db,
            admin,
        )
        assert result.stage == ReleaseStage.BETA
        assert result.organization_ids == [org.id]

        audit = db.query(AuditLog).filter(AuditLog.entity_type == "release_gate").one()
        assert audit.platform_user_id == admin.id
        assert audit.user_id is None
        assert '"stage":"HIDDEN"' in (audit.old_value or "")
        assert '"stage":"BETA"' in (audit.new_value or "")
    finally:
        db.close()
        engine.dispose()


def test_non_release_manager_cannot_change_gate() -> None:
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        gate = ReleaseGate(key="release.example", stage=ReleaseStage.HIDDEN)
        db.add(gate)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            update_release_gate(
                "release.example",
                ReleaseGateUpdateIn(stage=ReleaseStage.ALL_ORGS),
                db,
                support,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_registry_seed_is_idempotent_and_preserves_existing_stage(tmp_path: Path) -> None:
    db, engine = _session()
    try:
        registry = tmp_path / "FEATURE_REGISTRY.md"
        registry.write_text(
            "release.alpha release.beta\nrelease.alpha\n",
            encoding="utf-8",
        )
        db.add(ReleaseGate(key="release.alpha", stage=ReleaseStage.ALL_ORGS))
        db.commit()

        first_created, first_total = seed_release_gates(db, registry_path=registry)
        second_created, second_total = seed_release_gates(db, registry_path=registry)

        assert first_total == second_total == 2
        assert first_created == 1
        assert second_created == 0
        alpha = db.query(ReleaseGate).filter(ReleaseGate.key == "release.alpha").one()
        beta = db.query(ReleaseGate).filter(ReleaseGate.key == "release.beta").one()
        assert alpha.stage == ReleaseStage.ALL_ORGS
        assert beta.stage == ReleaseStage.HIDDEN
    finally:
        db.close()
        engine.dispose()


def test_registry_key_extraction_deduplicates_and_sorts() -> None:
    assert extract_release_gate_keys(
        "release.zeta | release.alpha | release.zeta"
    ) == ["release.alpha", "release.zeta"]
