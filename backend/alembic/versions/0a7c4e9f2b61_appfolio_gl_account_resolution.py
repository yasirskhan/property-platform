"""Phase 4.13 typed GL Account staged-row resolution target."""

from alembic import op
import sqlalchemy as sa


revision = "0a7c4e9f2b61"
down_revision = "f58a2c4d6e91"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platform_migration_staged_rows") as batch:
        batch.add_column(
            sa.Column("resolution_target_gl_account_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_gl_account_resolution",
            "gl_accounts",
            ["resolution_target_gl_account_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_target_gl_account_id",
            ["resolution_target_gl_account_id"],
        )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for migration reconciliation history."
    )
