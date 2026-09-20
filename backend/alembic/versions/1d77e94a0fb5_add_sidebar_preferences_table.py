"""add sidebar_preferences table

Revision ID: 1d77e94a0fb5
Revises: 660bc48a3454
Create Date: 2026-09-19

Creates the sidebar_preferences table:
  - one row per organization
  - order:    JSON list of nav keys
  - hidden:   JSON list of nav keys
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1d77e94a0fb5"
down_revision: Union[str, Sequence[str], None] = "660bc48a3454"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sidebar_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("order", sa.JSON(), nullable=False),
        sa.Column("hidden", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sidebar_preferences_id"),
        "sidebar_preferences",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sidebar_preferences_organization_id"),
        "sidebar_preferences",
        ["organization_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sidebar_preferences_organization_id"),
        table_name="sidebar_preferences",
    )
    op.drop_index(
        op.f("ix_sidebar_preferences_id"),
        table_name="sidebar_preferences",
    )
    op.drop_table("sidebar_preferences")