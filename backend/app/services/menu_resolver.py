# ============================================================
# menu_resolver.py
# ------------------------------------------------------------
# The single source of truth for "what should this user see?"
#
# 4-layer resolution (every layer must pass for an item to show):
#
#   Layer 1: Plan gating        -> STUBBED to always-allow (Phase 1)
#   Layer 2: Role gating        -> menu_permissions table
#   Layer 3: User overrides     -> user_permissions table
#   Layer 4: Personal hiding    -> sidebar_preferences.hidden
#
# Hard rules enforced here (do not weaken without redesign):
#
#   * Layers 2, 3, 4 can only SUBTRACT visibility. Layer 3 with
#     visible=True cannot grant what Layer 2 denied.
#
#   * ADMIN role always sees everything. Its matrix is immutable
#     and user overrides on an admin user are ignored. This makes
#     it impossible for an admin to lock themselves out.
#
#   * If a parent key is hidden, all its children are hidden,
#     regardless of their own values.
#
#   * Role values are compared case-insensitively (the users.role
#     column has historically been mixed-case).
# ============================================================

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.constants.menu_keys import MENU_KEYS, DEFAULT_MATRIX
from app.models.menu_permission import MenuPermission
from app.models.user_permission import UserPermission
from app.models.sidebar_preference import SidebarPreference
from app.models.user import User


# ------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------

def _norm_role(role: Optional[str]) -> str:
    """Normalize a role string to uppercase. Empty/None -> ''."""
    if not role:
        return ""
    return role.strip().upper()


def _parent_of(menu_key: str) -> Optional[str]:
    """'ACCOUNTING.RECEIVABLES' -> 'ACCOUNTING'. Top-level -> None."""
    if "." in menu_key:
        return menu_key.split(".", 1)[0]
    return None


def _plan_allows(_menu_key: str, _org_id: Optional[int]) -> bool:
    """Layer 1. Stubbed to always-allow in Phase 1.

    When the Subscription & Billing module is built, this function
    will look up the org's plan and check the module catalog. For
    now it returns True for everything so the rest of the stack
    works end-to-end.
    """
    return True


# ------------------------------------------------------------
# Layer loaders
# ------------------------------------------------------------

def _load_role_matrix(
    db: Session, organization_id: int, role: str
) -> Dict[str, bool]:
    """Layer 2: {menu_key: visible} for this org+role.

    If the DB has no rows for a key (shouldn't happen after the
    seed migration), we fall back to DEFAULT_MATRIX so the system
    is never silently empty.
    """
    rows = (
        db.query(MenuPermission)
        .filter(
            MenuPermission.organization_id == organization_id,
            MenuPermission.role == role,
        )
        .all()
    )
    found = {r.menu_key: bool(r.visible) for r in rows}

    defaults = DEFAULT_MATRIX.get(role, set())
    result: Dict[str, bool] = {}
    for key in MENU_KEYS:
        if key in found:
            result[key] = found[key]
        else:
            result[key] = key in defaults
    return result


def _load_user_overrides(
    db: Session, user_id: int
) -> Dict[str, bool]:
    """Layer 3: {menu_key: visible} for THIS user only."""
    rows = (
        db.query(UserPermission)
        .filter(UserPermission.user_id == user_id)
        .all()
    )
    return {r.menu_key: bool(r.visible) for r in rows}


def _load_personal_prefs(
    db: Session, user_id: int
) -> Tuple[Set[str], List[str]]:
    """Layer 4: (hidden_set, order_list) for THIS user.

    The row is per-user now (after the migration), but we filter
    strictly by user_id so no legacy rows leak across users.
    """
    pref = (
        db.query(SidebarPreference)
        .filter(SidebarPreference.user_id == user_id)
        .first()
    )
    if not pref:
        return set(), []
    hidden = set(pref.hidden or [])
    order = list(pref.order or [])
    return hidden, order


# ------------------------------------------------------------
# The resolver
# ------------------------------------------------------------

def resolve_menu_for_user(
    db: Session, user: User
) -> List[Dict[str, object]]:
    """Return the resolved, ordered, visible menu items for `user`.

    Each item: {"key": str, "parent": str | None}
    Hidden items are dropped entirely (not returned with visible=False).
    """
    org_id = user.organization_id
    role = _norm_role(user.role)

    # No org -> nothing to resolve. Return empty; the frontend will
    # fall back to a minimal placeholder sidebar.
    if org_id is None or not role:
        return []

    # ---- Layer 2 ----
    role_matrix = _load_role_matrix(db, org_id, role)

    # ---- Hard rule: ADMIN sees everything, always ----
    if role == "ADMIN":
        role_matrix = {k: True for k in MENU_KEYS}

    # ---- Layer 3 ----
    overrides = _load_user_overrides(db, user.id)

    # Admin users cannot have overrides applied (self-lockout guard)
    if role == "ADMIN":
        overrides = {}

    # ---- Layer 4 ----
    personal_hidden, personal_order = _load_personal_prefs(db, user.id)

    # ---- Combine ----
    effective: Dict[str, bool] = {}

    for key in MENU_KEYS:
        # Layer 1
        if not _plan_allows(key, org_id):
            effective[key] = False
            continue

        # Layer 2 (start point)
        allowed = role_matrix.get(key, False)
        if not allowed:
            effective[key] = False
            continue

        # Layer 3 — can only subtract. True here means "keep allowed".
        if key in overrides:
            if overrides[key] is False:
                effective[key] = False
                continue

        # Layer 4 — can only subtract.
        if key in personal_hidden:
            effective[key] = False
            continue

        effective[key] = True

    # ---- Parent-hidden rule ----
    # If a parent is hidden, force all children hidden.
    for key in MENU_KEYS:
        parent = _parent_of(key)
        if parent is not None and not effective.get(parent, False):
            effective[key] = False

    # ---- Build ordered list ----
    # Personal order first (any keys there), then the remaining keys
    # in the canonical MENU_KEYS order. Only visible keys survive.
    ordered_keys: List[str] = []
    seen: Set[str] = set()

    for key in personal_order:
        if key in MENU_KEYS and effective.get(key, False) and key not in seen:
            ordered_keys.append(key)
            seen.add(key)

    for key in MENU_KEYS:
        if effective.get(key, False) and key not in seen:
            ordered_keys.append(key)
            seen.add(key)

    return [
        {"key": k, "parent": _parent_of(k)}
        for k in ordered_keys
    ]


# ------------------------------------------------------------
# Admin/owner/manager scoping helper
# ------------------------------------------------------------

def can_edit_user(editor: User, target: User) -> bool:
    """Whether `editor` is allowed to change overrides for `target`.

    Rules:
      * Editor and target must be in the same org.
      * Editor must be ADMIN, OWNER, or MANAGER.
      * ADMIN can edit any non-admin user (and cannot edit other admins).
      * OWNER can edit any non-admin, non-owner user.
      * MANAGER can edit CREW/TENANT/VENDOR/VENDOR_CREW in their org.
        (Per-property scoping will be tightened once property_assignments
        is wired into this check; for now, same-org + role check.)
      * Nobody can edit an ADMIN except an ADMIN (and only to a
        non-admin role, which we don't allow here — so effectively
        nobody edits admins).
    """
    editor_role = _norm_role(editor.role)
    target_role = _norm_role(target.role)

    if editor.organization_id is None or target.organization_id is None:
        return False
    if editor.organization_id != target.organization_id:
        return False
    if editor.id == target.id:
        return False  # use My Preferences for self, not this endpoint

    if target_role == "ADMIN":
        return False  # admins are locked

    if editor_role == "ADMIN":
        return True
    if editor_role == "OWNER":
        return target_role in {"MANAGER", "CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT"}
    if editor_role == "MANAGER":
        return target_role in {"CREW", "TENANT", "VENDOR", "VENDOR_CREW"}
    return False


def editable_roles_for(editor: User) -> List[str]:
    """Which role columns this editor may edit in the Roles matrix.

    Admin never appears (immutable). Manager is limited to the four
    field roles they supervise.
    """
    role = _norm_role(editor.role)
    if role == "ADMIN":
        return ["OWNER", "MANAGER", "CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT"]
    if role == "OWNER":
        return ["MANAGER", "CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT"]
    if role == "MANAGER":
        return ["CREW", "TENANT", "VENDOR", "VENDOR_CREW"]
    return []