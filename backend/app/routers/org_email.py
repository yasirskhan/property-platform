# ============================================================
# routers/org_email.py
# ------------------------------------------------------------
#   GET    /organizations/{org_id}/email-settings
#   PUT    /organizations/{org_id}/email-settings
#   PATCH  /organizations/{org_id}/email-settings
#   DELETE /organizations/{org_id}/email-settings
#   POST   /organizations/{org_id}/email-settings/test
#   POST   /organizations/{org_id}/email-settings/disable
#   POST   /organizations/{org_id}/email-settings/enable
#
# Customer Admin and Owner can manage only their own organization.
# ============================================================

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import email as email_service
from app.core.crypto import encrypt
from app.core.database import get_db
from app.models.org_email import OrganizationEmailSettings
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.org_email import (
    OrgEmailSettingsCreate,
    OrgEmailSettingsUpdate,
    OrgEmailSettingsOut,
    TestEmailRequest,
    MessageResponse,
)


router = APIRouter(tags=["Organization Email"])


def _check_org_access(current_user: User, org_id: int):
    if (
        current_user.role in (UserRole.ADMIN, UserRole.OWNER)
        and current_user.organization_id == org_id
    ):
        return
    raise HTTPException(status_code=403, detail="Not allowed for this organization")


def _get_or_none(db: Session, org_id: int):
    return (
        db.query(OrganizationEmailSettings)
        .filter(OrganizationEmailSettings.organization_id == org_id)
        .first()
    )


@router.get(
    "/organizations/{org_id}/email-settings",
    response_model=OrgEmailSettingsOut,
)
def get_email_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)
    settings = _get_or_none(db, org_id)
    if not settings:
        raise HTTPException(status_code=404, detail="No custom email settings configured")
    return settings


@router.put(
    "/organizations/{org_id}/email-settings",
    response_model=OrgEmailSettingsOut,
)
def upsert_email_settings(
    org_id: int,
    payload: OrgEmailSettingsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)

    existing = _get_or_none(db, org_id)

    if existing:
        existing.from_email = payload.from_email
        existing.from_name = payload.from_name
        existing.reply_to_email = payload.reply_to_email
        existing.smtp_host = payload.smtp_host
        existing.smtp_port = payload.smtp_port
        existing.smtp_user = payload.smtp_user
        existing.smtp_password_encrypted = encrypt(payload.smtp_password)
        existing.smtp_use_tls = payload.smtp_use_tls
        existing.is_enabled = payload.is_enabled
        existing.verified_at = None
        existing.last_error = None
        db.commit()
        db.refresh(existing)
        return existing

    new_settings = OrganizationEmailSettings(
        organization_id=org_id,
        from_email=payload.from_email,
        from_name=payload.from_name,
        reply_to_email=payload.reply_to_email,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        smtp_user=payload.smtp_user,
        smtp_password_encrypted=encrypt(payload.smtp_password),
        smtp_use_tls=payload.smtp_use_tls,
        is_enabled=payload.is_enabled,
    )
    db.add(new_settings)
    db.commit()
    db.refresh(new_settings)
    return new_settings


@router.patch(
    "/organizations/{org_id}/email-settings",
    response_model=OrgEmailSettingsOut,
)
def update_email_settings(
    org_id: int,
    payload: OrgEmailSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)

    settings = _get_or_none(db, org_id)
    if not settings:
        raise HTTPException(status_code=404, detail="No custom email settings configured")

    changes = payload.model_dump(exclude_unset=True)

    if "smtp_password" in changes:
        settings.smtp_password_encrypted = encrypt(changes.pop("smtp_password"))
        settings.verified_at = None

    for field, value in changes.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.delete(
    "/organizations/{org_id}/email-settings",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_email_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)
    settings = _get_or_none(db, org_id)
    if settings:
        db.delete(settings)
        db.commit()
    return None


@router.post(
    "/organizations/{org_id}/email-settings/disable",
    response_model=MessageResponse,
)
def disable_email_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)
    settings = _get_or_none(db, org_id)
    if not settings:
        raise HTTPException(status_code=404, detail="No custom email settings configured")
    settings.is_enabled = False
    db.commit()
    return MessageResponse(detail="Custom email disabled. Platform default will be used.")


@router.post(
    "/organizations/{org_id}/email-settings/enable",
    response_model=MessageResponse,
)
def enable_email_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)
    settings = _get_or_none(db, org_id)
    if not settings:
        raise HTTPException(status_code=404, detail="No custom email settings configured")
    settings.is_enabled = True
    db.commit()
    return MessageResponse(detail="Custom email enabled.")


@router.post(
    "/organizations/{org_id}/email-settings/test",
    response_model=MessageResponse,
)
def test_email_settings(
    org_id: int,
    payload: TestEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_org_access(current_user, org_id)
    settings = _get_or_none(db, org_id)
    if not settings:
        raise HTTPException(status_code=404, detail="No custom email settings configured")

    settings.last_test_at = datetime.utcnow()

    try:
        email_service.send_email(
            to=payload.to,
            subject="Test email from Property Platform",
            body=(
                "This is a test email confirming that your organization's "
                "email settings are working correctly.\n\n"
                "— Property Platform"
            ),
            organization_id=org_id,
            db=db,
        )
        settings.verified_at = datetime.utcnow()
        settings.last_error = None
        db.commit()
        return MessageResponse(detail=f"Test email sent to {payload.to}.")
    except Exception as e:
        settings.last_error = str(e)[:500]
        db.commit()
        raise HTTPException(status_code=400, detail=f"Test failed: {e}")