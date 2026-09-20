# ============================================================
# menu_permissions.py (router)
# ------------------------------------------------------------
# All endpoints for the menu permission system.
#
#   GET    /api/menu/me                    resolved sidebar for me
#   GET    /api/menu/roles                 role matrix (editable subset)
#   PUT    /api/menu/roles/{role}          bulk-update one role's matrix
#   POST   /api/menu/roles/{role}/reset    reset one role to defaults
#   GET    /api/menu/users                 list users I can edit
#   GET    /api/menu/users/{user_id}       overrides for one user
#   PUT    /api/menu/users/{user_id}       batch-save user overrides
#   DELETE /api/menu/users/{user_id}/overrides   clear all overrides
#   GET    /api/menu/me/preferences        my personal prefs
#   PUT    /api/menu/me/preferences        save my personal prefs
#
# The resolver in app/services/menu_resolver.py is the only place
# that decides visibility. This router is thin glue.
# ============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.audit import log_action
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.menu_permission import MenuPermission
from app.models.user_permission import UserPermission
from app.models.sidebar_preference import SidebarPreference
from app.constants.menu_keys import (
    MENU_KEYS,
    DEFAULT_MATRIX,
    ROLES,
    IMMUTABLE_ROLES,
)
from app.services.menu_resolver import (
    resolve_menu_for_user,
    can_edit_user,
    editable_roles_for,
    _norm_role,
    _parent_of,
)
from app.schemas.menu_permission import (
    ResolvedMenuOut,
    ResolvedMenuItem,
    RoleMatrixOut,
    RoleMatrixRow,
    RoleMatrixUpdateIn,
    UserOverridesOut,
    UserOverrideRow,
    UserOverridesUpdateIn,
    MyPreferencesOut,
    MyPreferencesIn,
    EditableUserSummary,
)

router = APIRouter(prefix="/api/menu", tags=["Menu Permissions"])


# ------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------

def _require_role_editor(current_user: User, role: str) -> None:
    """Raise 403 if current_user cannot edit the given role."""
    role = _norm_role(role)
    if role in IMMUTABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is immutable and cannot be edited.",
        )
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role: {role}",
        )
    allowed = editable_roles_for(current_user)
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not allowed to edit the {role} role.",
        )


# ============================================================
# 1. GET /api/menu/me  — resolved sidebar for current user
# ============================================================

@router.get("/me", response_model=ResolvedMenuOut)
def get_my_menu(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = resolve_menu_for_user(db, current_user)
    return ResolvedMenuOut(
        items=[ResolvedMenuItem(**it) for it in items],
        role=_norm_role(current_user.role),
        organization_id=current_user.organization_id,
    )


# ============================================================
# 2. GET /api/menu/roles  — role matrix (editable subset)
# ============================================================

@router.get("/roles", response_model=RoleMatrixOut)
def get_role_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")

    editable = editable_roles_for(current_user)
    if not editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to edit role permissions.",
        )

    rows = (
        db.query(MenuPermission)
        .filter(
            MenuPermission.organization_id == current_user.organization_id,
            MenuPermission.role.in_(editable),
        )
        .all()
    )

    by_role_key = {(r.role, r.menu_key): bool(r.visible) for r in rows}

    out_rows: List[RoleMatrixRow] = []
    for key in MENU_KEYS:
        values = {}
        for role in editable:
            if (role, key) in by_role_key:
                values[role] = by_role_key[(role, key)]
            else:
                values[role] = key in DEFAULT_MATRIX.get(role, set())
        out_rows.append(
            RoleMatrixRow(
                menu_key=key,
                parent=_parent_of(key),
                values=values,
            )
        )

    return RoleMatrixOut(editable_roles=editable, rows=out_rows)


# ============================================================
# 3. PUT /api/menu/roles/{role}  — bulk-update one role's matrix
# ============================================================

@router.put("/roles/{role}", response_model=RoleMatrixOut)
def update_role_matrix(
    role: str,
    payload: RoleMatrixUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role_editor(current_user, role)
    role = _norm_role(role)

    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")

    bad_keys = [k for k in payload.values.keys() if k not in MENU_KEYS]
    if bad_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown menu keys: {bad_keys}",
        )

    existing = {
        r.menu_key: r
        for r in db.query(MenuPermission).filter(
            MenuPermission.organization_id == current_user.organization_id,
            MenuPermission.role == role,
        ).all()
    }

    for key, visible in payload.values.items():
        row = existing.get(key)
        if row is None:
            row = MenuPermission(
                organization_id=current_user.organization_id,
                role=role,
                menu_key=key,
                visible=bool(visible),
            )
            db.add(row)
        else:
            old = bool(row.visible)
            row.visible = bool(visible)
            if old != bool(visible):
                log_action(
                    db=db,
                    user=current_user,
                    entity_type="menu_permission",
                    entity_id=row.id or 0,
                    action="update",
                    field_name=key,
                    old_value=old,
                    new_value=bool(visible),
                )

    db.commit()

    return get_role_matrix(db=db, current_user=current_user)


# ============================================================
# 4. POST /api/menu/roles/{role}/reset  — reset role to defaults
# ============================================================

@router.post("/roles/{role}/reset", response_model=RoleMatrixOut)
def reset_role_matrix(
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role_editor(current_user, role)
    role = _norm_role(role)

    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")

    defaults = DEFAULT_MATRIX.get(role, set())

    existing = {
        r.menu_key: r
        for r in db.query(MenuPermission).filter(
            MenuPermission.organization_id == current_user.organization_id,
            MenuPermission.role == role,
        ).all()
    }

    for key in MENU_KEYS:
        want = key in defaults
        row = existing.get(key)
        if row is None:
            row = MenuPermission(
                organization_id=current_user.organization_id,
                role=role,
                menu_key=key,
                visible=want,
            )
            db.add(row)
        else:
            row.visible = want

    db.commit()

    log_action(
        db=db,
        user=current_user,
        entity_type="menu_permission",
        entity_id=0,
        action="reset_role",
        field_name=role,
        old_value=None,
        new_value="defaults",
    )

    return get_role_matrix(db=db, current_user=current_user)


# ============================================================
# 5. GET /api/menu/users  — list users I can edit
# ============================================================

@router.get("/users", response_model=List[EditableUserSummary])
def list_editable_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        return []

    candidates = (
        db.query(User)
        .filter(User.organization_id == current_user.organization_id)
        .all()
    )

    out: List[EditableUserSummary] = []
    for u in candidates:
        if can_edit_user(current_user, u):
            out.append(
                EditableUserSummary(
                    id=u.id,
                    email=u.email,
                    first_name=u.first_name or "",
                    last_name=u.last_name or "",
                    role=_norm_role(u.role),
                    organization_id=u.organization_id,
                )
            )
    return out


# ============================================================
# 6. GET /api/menu/users/{user_id}  — overrides for one user
# ============================================================

@router.get("/users/{user_id}", response_model=UserOverridesOut)
def get_user_overrides(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if not can_edit_user(current_user, target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to edit this user's permissions.",
        )

    target_role = _norm_role(target.role)

    role_rows = (
        db.query(MenuPermission)
        .filter(
            MenuPermission.organization_id == target.organization_id,
            MenuPermission.role == target_role,
        )
        .all()
    )
    role_default = {r.menu_key: bool(r.visible) for r in role_rows}
    for key in MENU_KEYS:
        if key not in role_default:
            role_default[key] = key in DEFAULT_MATRIX.get(target_role, set())

    over_rows = (
        db.query(UserPermission)
        .filter(UserPermission.user_id == user_id)
        .all()
    )
    overrides = {r.menu_key: bool(r.visible) for r in over_rows}

    rows: List[UserOverrideRow] = []
    for key in MENU_KEYS:
        rd = role_default.get(key, False)
        ov = overrides.get(key, None)
        if ov is None:
            eff = rd
        elif ov is False:
            eff = False
        else:
            eff = rd
        rows.append(
            UserOverrideRow(
                menu_key=key,
                parent=_parent_of(key),
                role_default=rd,
                override=ov,
                effective=eff,
            )
        )

    return UserOverridesOut(user_id=user_id, role=target_role, rows=rows)


# ============================================================
# 7. PUT /api/menu/users/{user_id}  — batch-save overrides
# ============================================================

@router.put("/users/{user_id}", response_model=UserOverridesOut)
def update_user_overrides(
    user_id: int,
    payload: UserOverridesUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if not can_edit_user(current_user, target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to edit this user's permissions.",
        )

    bad_keys = [k for k in payload.values.keys() if k not in MENU_KEYS]
    if bad_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown menu keys: {bad_keys}",
        )

    existing = {
        r.menu_key: r
        for r in db.query(UserPermission).filter(UserPermission.user_id == user_id).all()
    }

    for key, val in payload.values.items():
        if val is None:
            row = existing.get(key)
            if row is not None:
                db.delete(row)
            continue

        row = existing.get(key)
        if row is None:
            row = UserPermission(
                organization_id=target.organization_id,
                user_id=user_id,
                menu_key=key,
                visible=bool(val),
                set_by_user_id=current_user.id,
            )
            db.add(row)
        else:
            old = bool(row.visible)
            row.visible = bool(val)
            row.set_by_user_id = current_user.id
            if old != bool(val):
                log_action(
                    db=db,
                    user=current_user,
                    entity_type="user_permission",
                    entity_id=user_id,
                    action="update",
                    field_name=key,
                    old_value=old,
                    new_value=bool(val),
                )

    db.commit()

    return get_user_overrides(user_id=user_id, db=db, current_user=current_user)


# ============================================================
# 8. DELETE /api/menu/users/{user_id}/overrides  — clear all
# ============================================================

@router.delete("/users/{user_id}/overrides", status_code=204)
def clear_user_overrides(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if not can_edit_user(current_user, target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to edit this user's permissions.",
        )

    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
    db.commit()

    log_action(
        db=db,
        user=current_user,
        entity_type="user_permission",
        entity_id=user_id,
        action="clear_all_overrides",
        field_name=None,
        old_value=None,
        new_value=None,
    )
    return None


# ============================================================
# 9. GET /api/menu/me/preferences  — my personal prefs
# ============================================================

@router.get("/me/preferences", response_model=MyPreferencesOut)
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.user_id == current_user.id)
        .first()
    )
    if pref is None:
        return MyPreferencesOut(order=[], hidden=[], updated_at=None)
    return MyPreferencesOut(
        order=list(pref.order or []),
        hidden=list(pref.hidden or []),
        updated_at=pref.updated_at,
    )


# ============================================================
# 10. PUT /api/menu/me/preferences  — save my personal prefs
# ============================================================

@router.put("/me/preferences", response_model=MyPreferencesOut)
def update_my_preferences(
    payload: MyPreferencesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")

    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.user_id == current_user.id)
        .first()
    )

    if pref is None:
        pref = SidebarPreference(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            order=list(payload.order),
            hidden=list(payload.hidden),
        )
        db.add(pref)
    else:
        pref.order = list(payload.order)
        pref.hidden = list(payload.hidden)

    db.commit()
    db.refresh(pref)

    return MyPreferencesOut(
        order=list(pref.order or []),
        hidden=list(pref.hidden or []),
        updated_at=pref.updated_at,
    )