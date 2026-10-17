"""Phase 4.13 typed staged Tenant resolution target."""

from alembic import op
import sqlalchemy as sa


revision = "f58a2c4d6e91"
down_revision = "d46f1a7c9e20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platform_migration_staged_rows") as batch:
        batch.add_column(
            sa.Column("resolution_target_tenant_user_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_resolution_target_tenant_user_id",
            "users",
            ["resolution_target_tenant_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_target_tenant_user_id",
            ["resolution_target_tenant_user_id"],
        )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for staged Tenant resolution metadata."
    )
