"""sidebar_pref_user_id_not_null

Makes sidebar_preferences.user_id NOT NULL.

Before this migration, user_id was nullable (from the legacy
schema). The app always fills it, but the DB didn't enforce it.
This locks it down so a sidebar preference row always belongs
to a specific user.

Steps:
  1. Delete any orphan rows with user_id IS NULL (there shouldn't
     be any; the app has always set user_id since the model change).
  2. Rebuild the table with user_id INTEGER NOT NULL.

SQLite doesn't support ALTER COLUMN, so we rebuild via
batch_alter_table.

Revision ID: c0e4ac6f46b2
Revises: 3909fd7c7792
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "c0e4ac6f46b2"
down_revision = "3909fd7c7792"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Delete orphan rows (user_id NULL). Shouldn't exist, but be safe.
    conn.execute(sa.text("DELETE FROM sidebar_preferences WHERE user_id IS NULL"))

    # 2. Rebuild the table with user_id NOT NULL.
    #    batch_alter_table handles SQLite's lack of ALTER COLUMN.
    with op.batch_alter_table("sidebar_preferences") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("sidebar_preferences") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )