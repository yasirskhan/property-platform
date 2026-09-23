"""Release-stage and multi-layer capability access resolver.

Release control is intentionally independent from commercial entitlement,
organization configuration, authorization, and personal presentation.
A release gate can only deny/permit its own layer; it never grants another
layer. Non-applicable layers pass automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.release_gate import ReleaseGate, ReleaseGateOrganization, ReleaseStage


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    release_allowed: bool
    entitlement_allowed: bool
    org_config_allowed: bool
    permission_allowed: bool
    preference_allowed: bool
    reason: str | None = None


def release_gate_allows_org(
    db: Session,
    *,
    gate_key: str,
    organization_id: int | None,
) -> bool:
    """Resolve only the platform release-control layer.

    Missing gates and HIDDEN gates fail closed. ALL_ORGS passes every org.
    BETA and ROLLOUT currently use an explicit organization allowlist.
    """
    key = gate_key.strip()
    if not key:
        return False

    gate = db.query(ReleaseGate).filter(ReleaseGate.key == key).first()
    if gate is None:
        return False

    stage = gate.stage
    if isinstance(stage, str):
        stage = ReleaseStage(stage)

    if stage == ReleaseStage.HIDDEN:
        return False
    if stage == ReleaseStage.ALL_ORGS:
        return True
    if organization_id is None:
        return False

    return (
        db.query(ReleaseGateOrganization.id)
        .filter(
            ReleaseGateOrganization.release_gate_id == gate.id,
            ReleaseGateOrganization.organization_id == organization_id,
        )
        .first()
        is not None
    )


def resolve_capability_access(
    db: Session,
    *,
    gate_key: str,
    organization_id: int | None,
    entitlement_allowed: bool | None = None,
    org_config_allowed: bool | None = None,
    permission_allowed: bool | None = None,
    preference_allowed: bool | None = None,
) -> AccessDecision:
    """Compose all five independent access layers.

    For the four non-release layers, None means "not applicable" and passes.
    A concrete False means that layer denies access.
    """
    release_allowed = release_gate_allows_org(
        db,
        gate_key=gate_key,
        organization_id=organization_id,
    )
    entitlement_passes = entitlement_allowed is not False
    org_config_passes = org_config_allowed is not False
    permission_passes = permission_allowed is not False
    preference_passes = preference_allowed is not False

    checks = (
        ("release", release_allowed),
        ("entitlement", entitlement_passes),
        ("org_config", org_config_passes),
        ("permission", permission_passes),
        ("preference", preference_passes),
    )
    reason = next((name for name, passed in checks if not passed), None)

    return AccessDecision(
        allowed=all(passed for _, passed in checks),
        release_allowed=release_allowed,
        entitlement_allowed=entitlement_passes,
        org_config_allowed=org_config_passes,
        permission_allowed=permission_passes,
        preference_allowed=preference_passes,
        reason=reason,
    )
