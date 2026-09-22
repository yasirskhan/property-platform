"""drop_unique_org_index_sidebar

Drops the stale UNIQUE index on sidebar_preferences.organization_id
and recreates it as a plain (non-unique) index.

BACKGROUND

The sidebar_preferences table was originally designed as ONE ROW
PER ORGANIZATION. When the menu-permissions system was built
(Section 42), the design changed to ONE ROW PER USER. The
`user_id` column was added and given its own unique index, and
every consumer (menu_resolver, sidebar router, menu_permissions
router) was updated to query by user_id.

But the old `CREATE UNIQUE INDEX ix_sidebar_preferences_organization_id`
was never dropped. It enforces "one row per org" — which is why
the second user in an org cannot save their sidebar preferences:
their INSERT collides with the first user's row on the same org.

FIX

Drop the unique index. Recreate it as a plain index on the same
column so org-scoped queries stay fast. The unique constraint on
user_id is correct and stays.

Revision ID: 5949df11e460
Revises: c0e4ac6f46b2
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "5949df11e460"
down_revision = "c0e4ac6f46b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot alter an existing index in place.
    # Drop the unique index, then recreate as non-unique.
    op.drop_index(
        "ix_sidebar_preferences_organization_id",
        table_name="sidebar_preferences",
    )
    op.create_index(
        "ix_sidebar_preferences_organization_id",
        "sidebar_preferences",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sidebar_preferences_organization_id",
        table_name="sidebar_preferences",
    )
    op.create_index(
        "ix_sidebar_preferences_organization_id",
        "sidebar_preferences",
        ["organization_id"],
        unique=True,
    )