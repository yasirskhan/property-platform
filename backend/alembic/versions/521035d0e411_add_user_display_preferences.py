"""add_user_display_preferences

Adds the user_display_preferences table.
Per-user display settings: layout mode, theme, density,
date/number format, font size, accent color, reduce motion.

See PROJECT_MASTER.md Section 58.

Revision ID: 521035d0e411
Revises: 8c2e766863c0
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "521035d0e411"
down_revision = "8c2e766863c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_display_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("layout_mode", sa.String(length=20), nullable=False, server_default="TABS"),
        sa.Column("theme", sa.String(length=20), nullable=False, server_default="LIGHT"),
        sa.Column("density", sa.String(length=20), nullable=False, server_default="COMFORTABLE"),
        sa.Column("date_format", sa.String(length=20), nullable=False, server_default="US"),
        sa.Column("number_format", sa.String(length=20), nullable=False, server_default="US"),
        sa.Column("font_size", sa.String(length=20), nullable=False, server_default="NORMAL"),
        sa.Column("accent_color", sa.String(length=20), nullable=True),
        sa.Column("reduce_motion", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("user_display_preferences")