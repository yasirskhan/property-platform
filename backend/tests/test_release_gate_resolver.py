from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.release_gate import (
    ReleaseGate,
    ReleaseGateOrganization,
    ReleaseStage,
)
from app.models.user import Organization
from app.services.release_gate_resolver import (
    release_gate_allows_org,
    resolve_capability_access,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _org(db, slug: str) -> Organization:
    row = Organization(name=slug.title(), slug=slug)
    db.add(row)
    db.flush()
    return row


def test_missing_and_hidden_release_gates_fail_closed() -> None:
    db, engine = _session()
    try:
        org = _org(db, "one")
        db.add(ReleaseGate(key="release.hidden", stage=ReleaseStage.HIDDEN))
        db.commit()

        assert release_gate_allows_org(
            db,
            gate_key="release.missing",
            organization_id=org.id,
        ) is False
        assert release_gate_allows_org(
            db,
            gate_key="release.hidden",
            organization_id=org.id,
        ) is False
    finally:
        db.close()
        engine.dispose()


def test_all_orgs_release_gate_passes_without_allowlist() -> None:
    db, engine = _session()
    try:
        org = _org(db, "one")
        db.add(ReleaseGate(key="release.open", stage=ReleaseStage.ALL_ORGS))
        db.commit()

        assert release_gate_allows_org(
            db,
            gate_key="release.open",
            organization_id=org.id,
        ) is True
    finally:
        db.close()
        engine.dispose()


def test_beta_and_rollout_require_explicit_org_allowlist() -> None:
    db, engine = _session()
    try:
        allowed_org = _org(db, "allowed")
        blocked_org = _org(db, "blocked")
        beta = ReleaseGate(key="release.beta", stage=ReleaseStage.BETA)
        rollout = ReleaseGate(key="release.rollout", stage=ReleaseStage.ROLLOUT)
        db.add_all([beta, rollout])
        db.flush()
        db.add_all(
            [
                ReleaseGateOrganization(
                    release_gate_id=beta.id,
                    organization_id=allowed_org.id,
                ),
                ReleaseGateOrganization(
                    release_gate_id=rollout.id,
                    organization_id=allowed_org.id,
                ),
            ]
        )
        db.commit()

        for key in ("release.beta", "release.rollout"):
            assert release_gate_allows_org(
                db,
                gate_key=key,
                organization_id=allowed_org.id,
            ) is True
            assert release_gate_allows_org(
                db,
                gate_key=key,
                organization_id=blocked_org.id,
            ) is False
    finally:
        db.close()
        engine.dispose()


def test_non_applicable_layers_pass_but_any_explicit_false_denies() -> None:
    db, engine = _session()
    try:
        org = _org(db, "one")
        db.add(ReleaseGate(key="release.open", stage=ReleaseStage.ALL_ORGS))
        db.commit()

        open_decision = resolve_capability_access(
            db,
            gate_key="release.open",
            organization_id=org.id,
        )
        assert open_decision.allowed is True
        assert open_decision.reason is None

        denied = resolve_capability_access(
            db,
            gate_key="release.open",
            organization_id=org.id,
            entitlement_allowed=True,
            org_config_allowed=True,
            permission_allowed=False,
            preference_allowed=True,
        )
        assert denied.allowed is False
        assert denied.release_allowed is True
        assert denied.permission_allowed is False
        assert denied.reason == "permission"
    finally:
        db.close()
        engine.dispose()


def test_release_layer_never_grants_other_layers() -> None:
    db, engine = _session()
    try:
        org = _org(db, "one")
        db.add(ReleaseGate(key="release.open", stage=ReleaseStage.ALL_ORGS))
        db.commit()

        for layer in (
            "entitlement_allowed",
            "org_config_allowed",
            "permission_allowed",
            "preference_allowed",
        ):
            kwargs = {
                "entitlement_allowed": True,
                "org_config_allowed": True,
                "permission_allowed": True,
                "preference_allowed": True,
            }
            kwargs[layer] = False
            decision = resolve_capability_access(
                db,
                gate_key="release.open",
                organization_id=org.id,
                **kwargs,
            )
            assert decision.allowed is False
    finally:
        db.close()
        engine.dispose()
