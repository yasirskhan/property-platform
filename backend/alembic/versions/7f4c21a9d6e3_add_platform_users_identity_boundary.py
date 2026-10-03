"""add platform users identity boundary

Revision ID: 7f4c21a9d6e3
Revises: 5949df11e460
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "7f4c21a9d6e3"
down_revision = "5949df11e460"
branch_labels = None
depends_on = None


platform_user_role = sa.Enum(
    "platform_admin",
    "platform_sales",
    "platform_billing",
    "platform_tech",
    "platform_support",
    "platform_dev",
    name="platform_user_role",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "platform_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("role", platform_user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_users_id", "platform_users", ["id"], unique=False)
    op.create_index("ix_platform_users_email", "platform_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_platform_users_email", table_name="platform_users")
    op.drop_index("ix_platform_users_id", table_name="platform_users")
    op.drop_table("platform_users")
