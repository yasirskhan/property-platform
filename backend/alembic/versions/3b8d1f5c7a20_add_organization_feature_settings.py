"""add organization feature settings

Revision ID: 3b8d1f5c7a20
Revises: 6f1a9c4d2e7b
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "3b8d1f5c7a20"
down_revision = "6f1a9c4d2e7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_feature_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("feature_key", sa.String(length=200), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "feature_key",
            name="uq_organization_feature_setting",
        ),
    )
    op.create_index(
        "ix_organization_feature_settings_organization_id",
        "organization_feature_settings",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_feature_settings_feature_key",
        "organization_feature_settings",
        ["feature_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_feature_settings_feature_key",
        table_name="organization_feature_settings",
    )
    op.drop_index(
        "ix_organization_feature_settings_organization_id",
        table_name="organization_feature_settings",
    )
    op.drop_table("organization_feature_settings")
