"""Customer capability resolution for Phase 3.4.11."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.organization_features import (
    FEATURE_DEFINITIONS,
    SETTINGS_FEATURES_GATE,
)
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.user import User
from app.services.entitlement_resolver import resolve_entitlements
from app.services.menu_resolver import permission_allows_user
from app.services.release_gate_resolver import resolve_release_gates_for_org


@dataclass(frozen=True)
class CustomerFeatureDecision:
    key: str
    label: str
    allowed: bool
    release_allowed: bool
    entitlement_allowed: bool
    org_config_allowed: bool
    permission_allowed: bool
    org_configurable: bool


def resolve_customer_features(
    db: Session,
    *,
    user: User,
) -> list[CustomerFeatureDecision]:
    organization_id = user.organization_id
    if organization_id is None:
        return []

    release_matrix = resolve_release_gates_for_org(
        db,
        gate_keys=list(FEATURE_DEFINITIONS),
        organization_id=organization_id,
    )
    entitlement_keys = sorted(
        {
            str(meta["entitlement"])
            for meta in FEATURE_DEFINITIONS.values()
            if meta.get("entitlement") not in ("", "core")
        }
    )
    entitlement_matrix = resolve_entitlements(
        db,
        organization_id=organization_id,
        feature_keys=entitlement_keys,
    )
    settings = {
        row.feature_key: bool(row.enabled)
        for row in db.query(OrganizationFeatureSetting)
        .filter(OrganizationFeatureSetting.organization_id == organization_id)
        .all()
    }
    permission_cache: dict[str, bool] = {}

    decisions: list[CustomerFeatureDecision] = []
    for key, meta in FEATURE_DEFINITIONS.items():
        release_allowed = release_matrix.get(key, False)
        entitlement_key = str(meta.get("entitlement") or "")
        entitlement_allowed = (
            True
            if entitlement_key in ("", "core")
            else entitlement_matrix.get(entitlement_key, True)
        )

        org_configurable = bool(meta.get("org_configurable"))
        if key == SETTINGS_FEATURES_GATE:
            org_config_allowed = True
        elif org_configurable:
            org_config_allowed = settings.get(key, True)
        else:
            org_config_allowed = True

        permission_key = str(meta.get("permission") or "")
        if permission_key:
            if permission_key not in permission_cache:
                permission_cache[permission_key] = permission_allows_user(
                    db,
                    user=user,
                    menu_key=permission_key,
                )
            permission_allowed = permission_cache[permission_key]
        else:
            permission_allowed = True

        allowed = (
            release_allowed
            and entitlement_allowed
            and org_config_allowed
            and permission_allowed
        )
        decisions.append(
            CustomerFeatureDecision(
                key=key,
                label=str(meta["label"]),
                allowed=allowed,
                release_allowed=release_allowed,
                entitlement_allowed=entitlement_allowed,
                org_config_allowed=org_config_allowed,
                permission_allowed=permission_allowed,
                org_configurable=org_configurable,
            )
        )
    return decisions
