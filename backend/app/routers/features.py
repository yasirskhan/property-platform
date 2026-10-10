"""Customer feature/capability API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.constants.organization_features import (
    FEATURE_DEFINITIONS,
    SETTINGS_FEATURES_GATE,
)
from app.core.database import get_db
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.features import (
    FeatureDecisionOut,
    FeatureSettingOut,
    FeatureSettingsOut,
    FeatureSettingUpdateIn,
    MyFeaturesOut,
)
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.release_gate_resolver import release_gate_allows_org


router = APIRouter(prefix="/api/features", tags=["Customer Features"])


def _role_value(user: User) -> str:
    role = getattr(user.role, "value", user.role)
    return str(role or "").upper()


def _require_org(user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    return user.organization_id


def _require_feature_admin(user: User) -> int:
    organization_id = _require_org(user)
    if _role_value(user) not in {"ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner required.",
        )
    return organization_id


def _require_features_surface(db: Session, user: User) -> int:
    organization_id = _require_feature_admin(user)
    if not release_gate_allows_org(
        db,
        gate_key=SETTINGS_FEATURES_GATE,
        organization_id=organization_id,
    ):
        raise HTTPException(status_code=404, detail="Feature settings not available.")
    return organization_id


def _decision_out(item) -> FeatureDecisionOut:
    return FeatureDecisionOut(
        key=item.key,
        label=item.label,
        allowed=item.allowed,
        release_allowed=item.release_allowed,
        entitlement_allowed=item.entitlement_allowed,
        org_config_allowed=item.org_config_allowed,
        permission_allowed=item.permission_allowed,
        org_configurable=item.org_configurable,
    )


@router.get("/me", response_model=MyFeaturesOut)
def get_my_features(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org(current_user)
    released = [
        item
        for item in resolve_customer_features(db, user=current_user)
        if item.release_allowed
    ]
    return MyFeaturesOut(
        flags={item.key: item.allowed for item in released},
        features=[_decision_out(item) for item in released],
    )


@router.get("/settings", response_model=FeatureSettingsOut)
def get_feature_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_features_surface(db, current_user)
    stored = {
        row.feature_key: bool(row.enabled)
        for row in db.query(OrganizationFeatureSetting)
        .filter(OrganizationFeatureSetting.organization_id == organization_id)
        .all()
    }
    items = []
    for item in resolve_customer_features(db, user=current_user):
        if (
            not item.release_allowed
            or not item.org_configurable
            or item.key == SETTINGS_FEATURES_GATE
        ):
            continue
        items.append(
            FeatureSettingOut(
                **_decision_out(item).model_dump(),
                enabled=stored.get(item.key, True),
            )
        )
    return FeatureSettingsOut(items=sorted(items, key=lambda row: row.label.lower()))


@router.put("/settings/{feature_key:path}", response_model=FeatureSettingOut)
def update_feature_setting(
    feature_key: str,
    payload: FeatureSettingUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_features_surface(db, current_user)
    meta = FEATURE_DEFINITIONS.get(feature_key)
    if (
        meta is None
        or not bool(meta.get("org_configurable"))
        or feature_key == SETTINGS_FEATURES_GATE
    ):
        raise HTTPException(status_code=400, detail="Feature is not configurable.")

    if not release_gate_allows_org(
        db,
        gate_key=feature_key,
        organization_id=organization_id,
    ):
        raise HTTPException(status_code=404, detail="Feature is not available.")

    row = (
        db.query(OrganizationFeatureSetting)
        .filter(
            OrganizationFeatureSetting.organization_id == organization_id,
            OrganizationFeatureSetting.feature_key == feature_key,
        )
        .first()
    )
    old_enabled = True if row is None else bool(row.enabled)
    if row is None:
        row = OrganizationFeatureSetting(
            organization_id=organization_id,
            feature_key=feature_key,
            enabled=payload.enabled,
        )
        db.add(row)
    else:
        row.enabled = payload.enabled
    db.flush()

    if old_enabled != payload.enabled:
        append_audit_log(
            db,
            user_id=current_user.id,
            organization_id=organization_id,
            entity_type="organization_feature_setting",
            entity_id=row.id,
            action="updated",
            field_name=feature_key,
            old_value=old_enabled,
            new_value=payload.enabled,
        )
    db.commit()

    decision = next(
        item
        for item in resolve_customer_features(db, user=current_user)
        if item.key == feature_key
    )
    return FeatureSettingOut(
        **_decision_out(decision).model_dump(),
        enabled=bool(row.enabled),
    )
