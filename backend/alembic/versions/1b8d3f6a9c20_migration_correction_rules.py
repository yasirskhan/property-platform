"""Phase 4.13 run-scoped migration correction rules."""

from alembic import op
import sqlalchemy as sa


revision = "1b8d3f6a9c20"
down_revision = "0a7c4e9f2b61"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platform_migration_staged_rows") as batch:
        batch.add_column(
            sa.Column(
                "correction_evidence",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.create_table(
        "platform_migration_correction_rules",
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
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("source_value", sa.String(length=500), nullable=False),
        sa.Column("corrected_value", sa.String(length=500), nullable=False),
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
            "field_name",
            "source_value",
            name="uq_platform_migration_correction_rule_source",
        ),
    )
    op.create_index(
        "ix_platform_migration_correction_rules_run_id",
        "platform_migration_correction_rules",
        ["run_id"],
    )
    op.create_index(
        "ix_platform_migration_correction_rules_organization_id",
        "platform_migration_correction_rules",
        ["organization_id"],
    )
    op.create_index(
        "ix_platform_migration_correction_rules_provider",
        "platform_migration_correction_rules",
        ["provider"],
    )
    op.create_index(
        "ix_platform_migration_correction_rules_resource",
        "platform_migration_correction_rules",
        ["resource"],
    )
    op.create_index(
        "ix_platform_migration_correction_rules_created_by_platform_user_id",
        "platform_migration_correction_rules",
        ["created_by_platform_user_id"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for migration correction rules."
    )
