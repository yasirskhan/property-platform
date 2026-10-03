"""Track taxpayer/W-9 content changes separately from ciphertext key rotation.

Revision ID: f8c0d2e4a6b9
Revises: e7b9c1d3f5a8
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "f8c0d2e4a6b9"
down_revision = "e7b9c1d3f5a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_profiles",
        sa.Column("profile_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "tax_1099_reviews",
        sa.Column("reviewed_payer_revision", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tax_1099_reviews",
        sa.Column("reviewed_recipient_revision", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tax_1099_reviews", "reviewed_recipient_revision")
    op.drop_column("tax_1099_reviews", "reviewed_payer_revision")
    op.drop_column("tax_profiles", "profile_revision")
