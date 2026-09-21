"""add_settings_menu_keys

Seeds the new SETTINGS.* menu keys for every existing organization.

New keys:
  SETTINGS             (top-level parent)
  SETTINGS.DISPLAY
  SETTINGS.CURRENCIES
  SETTINGS.PERMISSIONS
  SETTINGS.SIDEBAR

Visibility defaults per role (matches menu_keys.py DEFAULT_MATRIX):
  ADMIN     -> all visible
  OWNER     -> all visible
  MANAGER   -> SETTINGS + SETTINGS.DISPLAY visible
  CREW      -> SETTINGS + SETTINGS.DISPLAY visible
  TENANT    -> SETTINGS + SETTINGS.DISPLAY visible
  VENDOR    -> SETTINGS + SETTINGS.DISPLAY visible
  VENDOR_CREW -> SETTINGS + SETTINGS.DISPLAY visible
  APPLICANT -> hidden

Idempotent: skips any (org, role, key) row that already exists.

Revision ID: 15d92d8a1eea
Revises: 521035d0e411
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "15d92d8a1eea"
down_revision = "521035d0e411"
branch_labels = None
depends_on = None


NEW_KEYS = [
    "SETTINGS",
    "SETTINGS.DISPLAY",
    "SETTINGS.CURRENCIES",
    "SETTINGS.PERMISSIONS",
    "SETTINGS.SIDEBAR",
]

# Which roles see which of the new keys by default.
# Anything not in the set is hidden for that role.
VISIBILITY = {
    "ADMIN":        set(NEW_KEYS),
    "OWNER":        set(NEW_KEYS),
    "MANAGER":      {"SETTINGS", "SETTINGS.DISPLAY"},
    "CREW":         {"SETTINGS", "SETTINGS.DISPLAY"},
    "TENANT":       {"SETTINGS", "SETTINGS.DISPLAY"},
    "VENDOR":       {"SETTINGS", "SETTINGS.DISPLAY"},
    "VENDOR_CREW":  {"SETTINGS", "SETTINGS.DISPLAY"},
    "APPLICANT":    set(),
}

ALL_ROLES = ["ADMIN", "OWNER", "MANAGER", "CREW", "TENANT",
             "VENDOR", "VENDOR_CREW", "APPLICANT"]


def upgrade() -> None:
    conn = op.get_bind()

    org_ids = [row[0] for row in conn.execute(
        sa.text("SELECT id FROM organizations")
    ).fetchall()]

    if not org_ids:
        return

    insert_sql = sa.text(
        """
        INSERT INTO menu_permissions
            (organization_id, role, menu_key, visible, created_at, updated_at)
        SELECT :org_id, :role, :menu_key, :visible,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM menu_permissions
            WHERE organization_id = :org_id
              AND role = :role
              AND menu_key = :menu_key
        )
        """
    )

    for org_id in org_ids:
        for role in ALL_ROLES:
            visible_set = VISIBILITY.get(role, set())
            for key in NEW_KEYS:
                conn.execute(
                    insert_sql,
                    {
                        "org_id": org_id,
                        "role": role,
                        "menu_key": key,
                        "visible": 1 if key in visible_set else 0,
                    },
                )


def downgrade() -> None:
    conn = op.get_bind()
    for key in NEW_KEYS:
        conn.execute(
            sa.text("DELETE FROM menu_permissions WHERE menu_key = :key"),
            {"key": key},
        )