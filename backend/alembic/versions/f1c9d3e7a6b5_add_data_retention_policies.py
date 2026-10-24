"""add data retention policies

Revision ID: f1c9d3e7a6b5
Revises: e0b8c2d6f5a4
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "f1c9d3e7a6b5"
down_revision = "e0b8c2d6f5a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_retention_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("data_class", sa.String(length=100), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "retention_days IS NULL OR retention_days IN (30, 365, 2555)",
            name="ck_retention_supported_window",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "data_class",
            name="uq_retention_org_data_class",
        ),
    )
    op.create_index(
        "ix_data_retention_policies_id",
        "data_retention_policies",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_data_retention_policies_organization_id",
        "data_retention_policies",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_data_retention_policies_data_class",
        "data_retention_policies",
        ["data_class"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_retention_policies_data_class",
        table_name="data_retention_policies",
    )
    op.drop_index(
        "ix_data_retention_policies_organization_id",
        table_name="data_retention_policies",
    )
    op.drop_index(
        "ix_data_retention_policies_id",
        table_name="data_retention_policies",
    )
    op.drop_table("data_retention_policies")
