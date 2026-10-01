"""Phase 4.13 staged AppFolio property resolution metadata."""

from alembic import op
import sqlalchemy as sa


revision = "b24d8c1f4a62"
down_revision = "f13c7a9e2b40"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "platform_migration_staged_rows",
        sa.Column("resolution_action", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "platform_migration_staged_rows",
        sa.Column(
            "resolution_target_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "platform_migration_staged_rows",
        sa.Column(
            "resolved_by_platform_user_id",
            sa.Integer(),
            sa.ForeignKey("platform_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "platform_migration_staged_rows",
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_platform_migration_staged_rows_resolution_action",
        "platform_migration_staged_rows",
        ["resolution_action"],
    )
    op.create_index(
        "ix_platform_migration_staged_rows_resolution_target_id",
        "platform_migration_staged_rows",
        ["resolution_target_id"],
    )
    op.create_index(
        "ix_platform_migration_staged_rows_resolved_by_platform_user_id",
        "platform_migration_staged_rows",
        ["resolved_by_platform_user_id"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for staged migration resolution metadata."
    )
