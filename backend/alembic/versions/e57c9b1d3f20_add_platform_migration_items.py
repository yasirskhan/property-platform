"""Phase 4.13 durable AppFolio source-to-target mappings."""

from alembic import op
import sqlalchemy as sa


revision = "e57c9b1d3f20"
down_revision = "d46f8a0c2e91"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_migration_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("platform_migration_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("target_entity", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_by_platform_user_id",
            sa.Integer(),
            sa.ForeignKey("platform_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "resource",
            "source_id",
            name="uq_platform_migration_item_source",
        ),
    )
    op.create_index("ix_platform_migration_items_run_id", "platform_migration_items", ["run_id"])
    op.create_index(
        "ix_platform_migration_items_organization_id",
        "platform_migration_items",
        ["organization_id"],
    )
    op.create_index("ix_platform_migration_items_provider", "platform_migration_items", ["provider"])
    op.create_index("ix_platform_migration_items_resource", "platform_migration_items", ["resource"])
    op.create_index("ix_platform_migration_items_target_id", "platform_migration_items", ["target_id"])
    op.create_index(
        "ix_platform_migration_items_source_fingerprint",
        "platform_migration_items",
        ["source_fingerprint"],
    )
    op.create_index(
        "ix_platform_migration_items_created_by_platform_user_id",
        "platform_migration_items",
        ["created_by_platform_user_id"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for platform migration mappings."
    )
