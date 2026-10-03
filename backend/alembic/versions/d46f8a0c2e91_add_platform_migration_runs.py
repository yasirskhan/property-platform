"""Phase 4.13 platform migration run metadata."""

from alembic import op
import sqlalchemy as sa


revision = "d46f8a0c2e91"
down_revision = "c35e7a9b1d4f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_migration_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_account_ref", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("last_dry_run_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("last_dry_run_summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_by_platform_user_id",
            sa.Integer(),
            sa.ForeignKey("platform_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_platform_migration_runs_organization_id",
        "platform_migration_runs",
        ["organization_id"],
    )
    op.create_index(
        "ix_platform_migration_runs_provider",
        "platform_migration_runs",
        ["provider"],
    )
    op.create_index(
        "ix_platform_migration_runs_status",
        "platform_migration_runs",
        ["status"],
    )
    op.create_index(
        "ix_platform_migration_runs_last_dry_run_fingerprint",
        "platform_migration_runs",
        ["last_dry_run_fingerprint"],
    )
    op.create_index(
        "ix_platform_migration_runs_created_by_platform_user_id",
        "platform_migration_runs",
        ["created_by_platform_user_id"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for platform migration history."
    )
