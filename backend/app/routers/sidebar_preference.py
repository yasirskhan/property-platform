# ============================================================
# sidebar_preference.py (router)
# ------------------------------------------------------------
# Endpoints:
#   GET  /settings/sidebar   -> current user's sidebar layout
#   PUT  /settings/sidebar   -> save the current user's layout
#
# Per-user. Each user has their own row. Absence of a row means
# "use defaults".
#
# See PROJECT_MASTER.md Sections 9 and 42.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.sidebar_preference import SidebarPreference
from app.schemas.sidebar_preference import (
    SidebarPreferenceIn,
    SidebarPreferenceOut,
)


router = APIRouter(prefix="/settings/sidebar", tags=["Sidebar Settings"])


# ------------------------------------------------------------
# GET - the current user's sidebar layout
# ------------------------------------------------------------
@router.get("", response_model=SidebarPreferenceOut | None)
def get_sidebar_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.user_id == current_user.id)
        .first()
    )
    if pref is None:
        return None

    return SidebarPreferenceOut(
        order=list(pref.order or []),
        hidden=list(pref.hidden or []),
        updated_at=pref.updated_at,
    )


# ------------------------------------------------------------
# PUT - save the current user's sidebar layout
# ------------------------------------------------------------
@router.put("", response_model=SidebarPreferenceOut)
def update_sidebar_preferences(
    payload: SidebarPreferenceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization",
        )

    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.user_id == current_user.id)
        .first()
    )

    if pref is None:
        try:
            pref = SidebarPreference(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                order=list(payload.order),
                hidden=list(payload.hidden),
            )
            db.add(pref)
            db.commit()
            db.refresh(pref)
        except IntegrityError:
            # Another request created it between our SELECT and INSERT.
            # Roll back and re-fetch.
            db.rollback()
            pref = (
                db.query(SidebarPreference)
                .filter(SidebarPreference.user_id == current_user.id)
                .first()
            )
            if pref is None:
                raise
            pref.order = list(payload.order)
            pref.hidden = list(payload.hidden)
            db.commit()
            db.refresh(pref)
    else:
        pref.order = list(payload.order)
        pref.hidden = list(payload.hidden)
        db.commit()
        db.refresh(pref)

    return SidebarPreferenceOut(
        order=list(pref.order or []),
        hidden=list(pref.hidden or []),
        updated_at=pref.updated_at,
    )