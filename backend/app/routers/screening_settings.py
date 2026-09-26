# ============================================================
# routers/screening_settings.py
# ------------------------------------------------------------
# Per-organization screening provider configuration.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.crypto import encrypt
from app.core.database import get_db
from app.models.screening import (
    ScreeningProvider,
    OrganizationScreeningSettings,
)
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.screening import (
    ScreeningProviderOut,
    ScreeningSettingsUpdate,
    ScreeningSettingsOut,
)


router = APIRouter(tags=["Screening"])


def _check_org_access(current_user: User, org_id: int):
    if (
        current_user.role in (UserRole.ADMIN, UserRole.OWNER)
        and current_user.organization_id == org_id
    ):
        return
    raise HTTPException(status_code=403, detail="Not allowed")


@router.get("/screening-providers", response_model=list[ScreeningProviderOut])
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ScreeningProvider).filter(ScreeningProvider.is_active == True).all()  # noqa: E712


@router.get(
    "/organizations/{org_id}/screening-settings",
    response_model=ScreeningSettingsOut,
)
def get_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)
    settings = (
        db.query(OrganizationScreeningSettings)
        .filter(OrganizationScreeningSettings.organization_id == org_id)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=404, detail="No screening settings configured")

    out = ScreeningSettingsOut.model_validate(settings)
    out.has_api_key = bool(settings.api_key_encrypted)
    out.has_api_secret = bool(settings.api_secret_encrypted)
    return out


@router.put(
    "/organizations/{org_id}/screening-settings",
    response_model=ScreeningSettingsOut,
)
def upsert_settings(
    org_id: int,
    payload: ScreeningSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)

    settings = (
        db.query(OrganizationScreeningSettings)
        .filter(OrganizationScreeningSettings.organization_id == org_id)
        .first()
    )

    if not settings:
        settings = OrganizationScreeningSettings(organization_id=org_id)
        db.add(settings)

    settings.provider_slug = payload.provider_slug
    settings.is_enabled = payload.is_enabled
    settings.application_fee = payload.application_fee
    settings.fee_waived_for_managers = payload.fee_waived_for_managers
    settings.auto_screen_on_apply = payload.auto_screen_on_apply
    settings.account_id = payload.account_id

    if payload.api_key:
        settings.api_key_encrypted = encrypt(payload.api_key)
    if payload.api_secret:
        settings.api_secret_encrypted = encrypt(payload.api_secret)

    db.commit()
    db.refresh(settings)

    out = ScreeningSettingsOut.model_validate(settings)
    out.has_api_key = bool(settings.api_key_encrypted)
    out.has_api_secret = bool(settings.api_secret_encrypted)
    return out