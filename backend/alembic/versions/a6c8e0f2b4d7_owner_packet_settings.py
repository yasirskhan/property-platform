"""add owner packet settings

Revision ID: a6c8e0f2b4d7
Revises: f5a7c9e1b3d6
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a6c8e0f2b4d7"
down_revision = "f5a7c9e1b3d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_packet_settings",
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "included_reports",
            sa.Text(),
            nullable=False,
            server_default='["OWNER_STATEMENT","PROPERTY_CASH_SUMMARY"]',
        ),
        sa.Column("email_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cover_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("owner_packet_settings")
