"""Phase 4.13 staged AppFolio property resolution metadata."""

from alembic import op
import sqlalchemy as sa


revision = "b24d8c1f4a62"
down_revision = "f13c7a9e2b40"
branch_labels = None
depends_on = None


def upgrade():
    # Batch mode keeps the legacy SQLite upgrade drill compatible while
    # preserving the same PostgreSQL foreign-key/index contract.
    with op.batch_alter_table("platform_migration_staged_rows") as batch:
        batch.add_column(
            sa.Column("resolution_action", sa.String(length=32), nullable=True)
        )
        batch.add_column(
            sa.Column("resolution_target_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("resolved_by_platform_user_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("resolved_at", sa.DateTime(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_resolution_target_id",
            "properties",
            ["resolution_target_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_resolved_by_platform_user_id",
            "platform_users",
            ["resolved_by_platform_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_action",
            ["resolution_action"],
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_target_id",
            ["resolution_target_id"],
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolved_by_platform_user_id",
            ["resolved_by_platform_user_id"],
        )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for staged migration resolution metadata."
    )
