"""Phase 4.13 typed staged Owner/Vendor resolution targets."""

from alembic import op
import sqlalchemy as sa


revision = "d46f1a7c9e20"
down_revision = "c35e9d2a7b14"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platform_migration_staged_rows") as batch:
        batch.add_column(
            sa.Column("resolution_target_owner_user_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("resolution_target_vendor_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_resolution_target_owner_user_id",
            "users",
            ["resolution_target_owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_resolution_target_vendor_id",
            "vendors",
            ["resolution_target_vendor_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_target_owner_user_id",
            ["resolution_target_owner_user_id"],
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_target_vendor_id",
            ["resolution_target_vendor_id"],
        )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for staged Owner/Vendor resolution metadata."
    )
