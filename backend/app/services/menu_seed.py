# ============================================================
# menu_seed.py
# ------------------------------------------------------------
# Seeds a brand-new organization's menu_permissions table with
# the default matrix from app/constants/menu_keys.py.
#
# Called once, inside the same DB transaction that creates the
# organization. If seeding fails, the whole signup rolls back —
# we never leave an org without a permission matrix, because
# that would make every user's sidebar empty.
#
# Idempotent: re-running on an org that already has rows will
# fill in any missing ones and leave existing rows untouched.
# Safe to call defensively.
# ============================================================

from sqlalchemy.orm import Session

from app.constants.menu_keys import MENU_KEYS, ROLES, DEFAULT_MATRIX
from app.models.menu_permission import MenuPermission


def seed_menu_permissions_for_org(db: Session, organization_id: int) -> int:
    """Create default menu_permissions rows for a new organization.

    Returns the number of NEW rows created (0 if the org was
    already fully seeded).
    """
    # Which (role, menu_key) pairs already exist?
    existing = {
        (r.role, r.menu_key)
        for r in db.query(MenuPermission)
        .filter(MenuPermission.organization_id == organization_id)
        .all()
    }

    created = 0
    for role in ROLES:
        allowed = DEFAULT_MATRIX.get(role, set())
        for key in MENU_KEYS:
            if (role, key) in existing:
                continue
            db.add(
                MenuPermission(
                    organization_id=organization_id,
                    role=role,
                    menu_key=key,
                    visible=key in allowed,
                )
            )
            created += 1

    # Caller controls the commit. We do NOT commit here so the
    # whole signup transaction is atomic.
    db.flush()
    return created