"""Current-user personal settings.

These preferences are intentionally not organization capability-gated. They are
self-service settings for the authenticated user and never grant access to
business data or features.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.user_personal_settings import UserPersonalSettings
from app.routers.auth import get_current_user
from app.schemas.user_personal_settings import MySettingsOut, MySettingsUpdate
from app.services.audit import append_audit_log


router = APIRouter(prefix="/api/settings/my", tags=["My Settings"])


def _org_id(user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    return user.organization_id


def _out(user: User, row: UserPersonalSettings | None) -> MySettingsOut:
    return MySettingsOut(
        user_id=user.id,
        organization_id=_org_id(user),
        email_notifications_enabled=(
            row.email_notifications_enabled if row is not None else True
        ),
        email_signature=row.email_signature if row is not None else None,
        reply_to_email=row.reply_to_email if row is not None else None,
        language_override=row.language_override if row is not None else None,
        export_format_override=(
            row.export_format_override if row is not None else None
        ),
    )


@router.get("", response_model=MySettingsOut)
def get_my_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _org_id(current_user)
    row = (
        db.query(UserPersonalSettings)
        .filter(UserPersonalSettings.user_id == current_user.id)
        .first()
    )
    return _out(current_user, row)


@router.put("", response_model=MySettingsOut)
def update_my_settings(
    payload: MySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _org_id(current_user)
    row = (
        db.query(UserPersonalSettings)
        .filter(UserPersonalSettings.user_id == current_user.id)
        .first()
    )
    old_value = None
    if row is None:
        row = UserPersonalSettings(
            user_id=current_user.id,
            organization_id=organization_id,
        )
        db.add(row)
    else:
        old_value = {
            "email_notifications_enabled": row.email_notifications_enabled,
            "email_signature": row.email_signature,
            "reply_to_email": row.reply_to_email,
            "language_override": row.language_override,
            "export_format_override": row.export_format_override,
        }

    values = payload.model_dump()
    values["reply_to_email"] = (
        str(values["reply_to_email"]) if values["reply_to_email"] is not None else None
    )
    for field, value in values.items():
        setattr(row, field, value)

    db.flush()
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=organization_id,
        entity_type="user_personal_settings",
        entity_id=current_user.id,
        action="updated",
        old_value=old_value,
        new_value=values,
    )
    db.commit()
    db.refresh(row)
    return _out(current_user, row)
