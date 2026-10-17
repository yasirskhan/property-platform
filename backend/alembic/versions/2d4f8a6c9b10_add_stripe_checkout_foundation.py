"""add stripe checkout session foundation

Revision ID: 2d4f8a6c9b10
Revises: 1be8d7f3a0c2
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "2d4f8a6c9b10"
down_revision = "1be8d7f3a0c2"
branch_labels = None
depends_on = None


checkout_status = sa.Enum(
    "PENDING",
    "CREATED",
    "COMPLETED",
    "EXPIRED",
    "FAILED",
    name="billing_checkout_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_stripe_subscription_id",
        "subscriptions",
        ["stripe_subscription_id"],
        unique=True,
    )

    op.create_table(
        "billing_checkout_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("pricing_tier_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="stripe",
            nullable=False,
        ),
        sa.Column("provider_session_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            checkout_status,
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["pricing_tier_id"],
            ["pricing_tiers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_billing_checkout_sessions_org_idempotency",
        ),
    )
    op.create_index(
        "ix_billing_checkout_sessions_organization_id",
        "billing_checkout_sessions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_billing_checkout_sessions_plan_id",
        "billing_checkout_sessions",
        ["plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_billing_checkout_sessions_pricing_tier_id",
        "billing_checkout_sessions",
        ["pricing_tier_id"],
        unique=False,
    )
    op.create_index(
        "ix_billing_checkout_sessions_requested_by_user_id",
        "billing_checkout_sessions",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_billing_checkout_sessions_provider_session_id",
        "billing_checkout_sessions",
        ["provider_session_id"],
        unique=True,
    )
    op.create_index(
        "ix_billing_checkout_sessions_status",
        "billing_checkout_sessions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_checkout_sessions_status",
        table_name="billing_checkout_sessions",
    )
    op.drop_index(
        "ix_billing_checkout_sessions_provider_session_id",
        table_name="billing_checkout_sessions",
    )
    op.drop_index(
        "ix_billing_checkout_sessions_requested_by_user_id",
        table_name="billing_checkout_sessions",
    )
    op.drop_index(
        "ix_billing_checkout_sessions_pricing_tier_id",
        table_name="billing_checkout_sessions",
    )
    op.drop_index(
        "ix_billing_checkout_sessions_plan_id",
        table_name="billing_checkout_sessions",
    )
    op.drop_index(
        "ix_billing_checkout_sessions_organization_id",
        table_name="billing_checkout_sessions",
    )
    op.drop_table("billing_checkout_sessions")
    op.drop_index(
        "ix_subscriptions_stripe_subscription_id",
        table_name="subscriptions",
    )
    op.drop_column("subscriptions", "stripe_subscription_id")
