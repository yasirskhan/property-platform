"""add user two-factor settings

Revision ID: e1b3d5f7a9c2
Revises: d9f1b3c5e7a0
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "e1b3d5f7a9c2"
down_revision = "d9f1b3c5e7a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_two_factor_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_user_two_factor_org_user"),
        sa.UniqueConstraint("user_id", name="uq_user_two_factor_user"),
    )
    op.create_index("ix_user_two_factor_settings_id", "user_two_factor_settings", ["id"], unique=False)
    op.create_index("ix_user_two_factor_settings_user_id", "user_two_factor_settings", ["user_id"], unique=True)
    op.create_index("ix_user_two_factor_settings_organization_id", "user_two_factor_settings", ["organization_id"], unique=False)
    op.create_index("ix_user_two_factor_settings_is_enabled", "user_two_factor_settings", ["is_enabled"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_two_factor_settings_is_enabled", table_name="user_two_factor_settings")
    op.drop_index("ix_user_two_factor_settings_organization_id", table_name="user_two_factor_settings")
    op.drop_index("ix_user_two_factor_settings_user_id", table_name="user_two_factor_settings")
    op.drop_index("ix_user_two_factor_settings_id", table_name="user_two_factor_settings")
    op.drop_table("user_two_factor_settings")
