"""add_charges_menu_key

Seeds the ACCOUNTING.CHARGES menu key for every existing org.

Visibility:
  ADMIN     -> visible
  OWNER     -> visible
  MANAGER   -> visible
  CREW      -> hidden
  TENANT    -> hidden
  VENDOR    -> hidden
  VENDOR_CREW -> hidden
  APPLICANT -> hidden

Idempotent: skips rows that already exist.

Revision ID: 3909fd7c7792
Revises: f49b93dcb1e2
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "3909fd7c7792"
down_revision = "f49b93dcb1e2"
branch_labels = None
depends_on = None


KEY = "ACCOUNTING.CHARGES"
VISIBLE_ROLES = {"ADMIN", "OWNER", "MANAGER"}
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
            conn.execute(insert_sql, {
                "org_id": org_id,
                "role": role,
                "menu_key": KEY,
                "visible": 1 if role in VISIBLE_ROLES else 0,
            })


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM menu_permissions WHERE menu_key = :key"),
        {"key": KEY},
    )