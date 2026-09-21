# ============================================================
# settings_display.py
# ------------------------------------------------------------
# Per-user display settings + per-org currency endpoints.
#
# GET  /api/settings/display   -> return current user's prefs
#                                (creates default row if missing)
# PUT  /api/settings/display   -> update prefs + org currency
#
# Currency is ORG-WIDE, not per-user. Saving via this endpoint
# requires ADMIN or OWNER role.
#
# See PROJECT_MASTER.md Section 58 and Section 59.
# ============================================================

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User, Organization
from app.models.user_display_preference import UserDisplayPreference


router = APIRouter(prefix="/api/settings", tags=["settings"])


# ------------------------------------------------------------
# Schemas
# ------------------------------------------------------------
class DisplayPreferences(BaseModel):
    layout_mode: str = Field("TABS", pattern="^(TABS|VERTICAL)$")
    theme: str = Field("LIGHT", pattern="^(LIGHT|DARK|AUTO)$")
    density: str = Field("COMFORTABLE", pattern="^(COMPACT|COMFORTABLE|SPACIOUS)$")
    date_format: str = Field("US", pattern="^(US|ISO|EU)$")
    number_format: str = Field("US", pattern="^(US|EU|SPACE)$")
    font_size: str = Field("NORMAL", pattern="^(SMALL|NORMAL|LARGE)$")
    accent_color: str | None = None
    reduce_motion: bool = False
    # Currency is accepted here so the Display page can save everything
    # in one round-trip. Only ADMIN/OWNER can actually change it; a
    # non-privileged save silently ignores the currency field.
    currency: str = Field("USD", pattern="^[A-Z]{3}$")


class DisplayResponse(DisplayPreferences):
    pass


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _get_or_create_prefs(db: Session, user: User) -> UserDisplayPreference:
    prefs = (
        db.query(UserDisplayPreference)
        .filter(UserDisplayPreference.user_id == user.id)
        .first()
    )
    if prefs is None:
        prefs = UserDisplayPreference(
            user_id=user.id,
            organization_id=user.organization_id,
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def _get_org(db: Session, user: User) -> Organization | None:
    if user.organization_id is None:
        return None
    return (
        db.query(Organization)
        .filter(Organization.id == user.organization_id)
        .first()
    )


def _org_currency(db: Session, user: User) -> str:
    org = _get_org(db, user)
    if org is None:
        return "USD"
    return getattr(org, "currency", None) or "USD"


def _build_response(prefs: UserDisplayPreference, currency: str) -> DisplayResponse:
    return DisplayResponse(
        layout_mode=prefs.layout_mode,
        theme=prefs.theme,
        density=prefs.density,
        date_format=prefs.date_format,
        number_format=prefs.number_format,
        font_size=prefs.font_size,
        accent_color=prefs.accent_color,
        reduce_motion=prefs.reduce_motion,
        currency=currency,
    )


# ------------------------------------------------------------
# GET /api/settings/display
# ------------------------------------------------------------
@router.get("/display", response_model=DisplayResponse)
def get_display(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prefs = _get_or_create_prefs(db, user)
    return _build_response(prefs, _org_currency(db, user))


# ------------------------------------------------------------
# PUT /api/settings/display
# ------------------------------------------------------------
@router.put("/display", response_model=DisplayResponse)
def update_display(
    payload: DisplayPreferences,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prefs = _get_or_create_prefs(db, user)

    prefs.layout_mode = payload.layout_mode
    prefs.theme = payload.theme
    prefs.density = payload.density
    prefs.date_format = payload.date_format
    prefs.number_format = payload.number_format
    prefs.font_size = payload.font_size
    prefs.accent_color = payload.accent_color
    prefs.reduce_motion = payload.reduce_motion
    prefs.updated_at = datetime.utcnow()

    db.add(prefs)

    # Currency is org-wide. Only ADMIN and OWNER can change it.
    new_currency = _org_currency(db, user)
    if payload.currency and payload.currency != new_currency:
        role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
        if role in ("ADMIN", "OWNER"):
            org = _get_org(db, user)
            if org is not None:
                org.currency = payload.currency
                db.add(org)
                new_currency = payload.currency
        # else: silently ignore - non-privileged user tried to change currency

    db.commit()
    db.refresh(prefs)
    return _build_response(prefs, new_currency)