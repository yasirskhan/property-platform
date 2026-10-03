"""add customer subscription foundation

Revision ID: c5a8e2f14b76
Revises: a4f7c2d9e813
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "c5a8e2f14b76"
down_revision = "a4f7c2d9e813"
branch_labels = None
depends_on = None

subscription_status = sa.Enum(
    "ACTIVE",
    "PAST_DUE",
    "RESTRICTED",
    "SUSPENDED",
    "CANCELLED",
    name="subscription_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            subscription_status,
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "current_period_end IS NULL OR current_period_start IS NULL "
            "OR current_period_end >= current_period_start",
            name="ck_subscriptions_period_range",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscriptions_organization_id",
        "subscriptions",
        ["organization_id"],
        unique=True,
    )
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"], unique=False)
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_organization_id", table_name="subscriptions")
    op.drop_table("subscriptions")
