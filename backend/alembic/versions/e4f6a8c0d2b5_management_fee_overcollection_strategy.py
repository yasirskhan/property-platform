"""management fee overcollection strategy

Revision ID: e4f6a8c0d2b5
Revises: d3f5a7c9e1b4
"""
from alembic import op
import sqlalchemy as sa

revision = "e4f6a8c0d2b5"
down_revision = "d3f5a7c9e1b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "management_fee_overcollection_strategy",
            sa.String(length=32),
            nullable=False,
            server_default="CREDITS_THEN_RECEIPTS",
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "management_fee_overcollection_strategy")
