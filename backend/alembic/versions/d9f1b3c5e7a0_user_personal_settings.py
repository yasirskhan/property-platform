"""add user personal settings

Revision ID: d9f1b3c5e7a0
Revises: c8e0a2b4d6f9
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa


revision = "d9f1b3c5e7a0"
down_revision = "c8e0a2b4d6f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_personal_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("email_signature", sa.Text(), nullable=True),
        sa.Column("reply_to_email", sa.String(length=255), nullable=True),
        sa.Column("language_override", sa.String(length=16), nullable=True),
        sa.Column("export_format_override", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_user_personal_settings_user_id",
        "user_personal_settings",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_user_personal_settings_organization_id",
        "user_personal_settings",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_personal_settings_organization_id",
        table_name="user_personal_settings",
    )
    op.drop_index(
        "ix_user_personal_settings_user_id",
        table_name="user_personal_settings",
    )
    op.drop_table("user_personal_settings")
