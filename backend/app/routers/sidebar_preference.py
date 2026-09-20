# ============================================================
# sidebar_preference.py (router)
# ------------------------------------------------------------
# Endpoints:
#   GET  /settings/sidebar   -> current org's sidebar layout
#   PUT  /settings/sidebar   -> save the layout (manager/admin/owner only)
#
# One row per organization. Auto-created on first save.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
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
# GET — read the current org's sidebar layout
# ------------------------------------------------------------
@router.get("", response_model=SidebarPreferenceOut | None)
def get_sidebar_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        return None

    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.organization_id == current_user.organization_id)
        .first()
    )

    if not pref:
        return None

    return SidebarPreferenceOut(
        order=pref.order or [],
        hidden=pref.hidden or [],
        updated_at=pref.updated_at,
    )


# ------------------------------------------------------------
# PUT — save the current org's sidebar layout
# ------------------------------------------------------------
@router.put("", response_model=SidebarPreferenceOut)
def update_sidebar_preferences(
    payload: SidebarPreferenceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "manager", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers, admins, and owners can customize the sidebar",
        )

    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization",
        )

    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.organization_id == current_user.organization_id)
        .first()
    )

    if pref:
        pref.order = payload.order
        pref.hidden = payload.hidden
    else:
        pref = SidebarPreference(
            organization_id=current_user.organization_id,
            order=payload.order,
            hidden=payload.hidden,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)

    return SidebarPreferenceOut(
        order=pref.order or [],
        hidden=pref.hidden or [],
        updated_at=pref.updated_at,
    )