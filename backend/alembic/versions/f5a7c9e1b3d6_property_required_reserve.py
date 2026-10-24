"""add required owner reserve to properties

Revision ID: f5a7c9e1b3d6
Revises: e4f6a8c0d2b5
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "f5a7c9e1b3d6"
down_revision = "e4f6a8c0d2b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column(
            "required_reserve_amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0.00",
        ),
    )


def downgrade() -> None:
    op.drop_column("properties", "required_reserve_amount")
