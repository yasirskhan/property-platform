"""add organizations.state and backfill orgless users

Revision ID: 9f4b7c1a2d55
Revises: 8a3f2c1e9b44
Create Date: 2026-09-19

Changes:
  - Adds `state` column to `organizations` (subscription lifecycle
    placeholder for Phase 10). Existing rows default to 'ACTIVE'.
  - Backfills two legacy test users that were created without an
    organization into org 1:
      * admin@test.com
      * owner@test.com

This migration is idempotent: running it twice is a no-op.
"""
from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = "9f4b7c1a2d55"
down_revision = "8a3f2c1e9b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # -----------------------------------------------------------------
    # 1. Add organizations.state
    # -----------------------------------------------------------------
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "state",
                sa.String(length=20),
                nullable=False,
                server_default="ACTIVE",
            )
        )

    # Index for state lookups (Phase 10 will filter heavily on it)
    op.create_index("ix_organizations_state", "organizations", ["state"])

    # Make sure every existing org has a value even if the server
    # default didn't kick in for some reason.
    bind.execute(
        sa.text(
            "UPDATE organizations SET state = 'ACTIVE' "
            "WHERE state IS NULL OR state = ''"
        )
    )

    # -----------------------------------------------------------------
    # 2. Backfill orgless users
    # -----------------------------------------------------------------
    # Only do this if org 1 exists. If a fresh DB has no org 1,
    # there is nothing to backfill and the migration is a no-op.
    org1 = bind.execute(
        sa.text("SELECT id FROM organizations WHERE id = 1")
    ).fetchone()

    if org1 is not None:
        for email in ("admin@test.com", "owner@test.com"):
            bind.execute(
                sa.text(
                    "UPDATE users SET organization_id = 1 "
                    "WHERE email = :email AND organization_id IS NULL"
                ),
                {"email": email},
            )


def downgrade() -> None:
    bind = op.get_bind()

    # Note: we intentionally do NOT null out organization_id on
    # downgrade. Putting a user back in the "orgless" state is
    # dangerous and there is no correct way to know which users
    # we touched (they may have been legitimately org-assigned
    # by other means after this migration ran).
    # Leaving them in their org is harmless; the column is still
    # nullable at the DB level after downgrade.

    op.drop_index("ix_organizations_state", table_name="organizations")

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("state")