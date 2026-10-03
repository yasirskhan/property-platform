"""add billing settings and payment methods

Revision ID: e8c1b4a6d903
Revises: d7e9a3c5f218
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "e8c1b4a6d903"
down_revision = "d7e9a3c5f218"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("billing_email", sa.String(length=255), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_billing_settings_organization_id",
        "billing_settings",
        ["organization_id"],
        unique=True,
    )
    op.create_index(
        "ix_billing_settings_stripe_customer_id",
        "billing_settings",
        ["stripe_customer_id"],
        unique=True,
    )

    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="stripe",
            nullable=False,
        ),
        sa.Column(
            "provider_payment_method_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("method_type", sa.String(length=32), nullable=False),
        sa.Column("brand", sa.String(length=50), nullable=True),
        sa.Column("last4", sa.String(length=4), nullable=True),
        sa.Column("exp_month", sa.Integer(), nullable=True),
        sa.Column("exp_year", sa.Integer(), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "last4 IS NULL OR length(last4) = 4",
            name="ck_payment_methods_last4",
        ),
        sa.CheckConstraint(
            "exp_month IS NULL OR (exp_month >= 1 AND exp_month <= 12)",
            name="ck_payment_methods_exp_month",
        ),
        sa.CheckConstraint(
            "exp_year IS NULL OR exp_year >= 2000",
            name="ck_payment_methods_exp_year",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payment_methods_organization_id",
        "payment_methods",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_methods_provider_payment_method_id",
        "payment_methods",
        ["provider_payment_method_id"],
        unique=True,
    )
    op.create_index(
        "ix_payment_methods_is_default",
        "payment_methods",
        ["is_default"],
        unique=False,
    )
    op.create_index(
        "ix_payment_methods_is_active",
        "payment_methods",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_methods_is_active",
        table_name="payment_methods",
    )
    op.drop_index(
        "ix_payment_methods_is_default",
        table_name="payment_methods",
    )
    op.drop_index(
        "ix_payment_methods_provider_payment_method_id",
        table_name="payment_methods",
    )
    op.drop_index(
        "ix_payment_methods_organization_id",
        table_name="payment_methods",
    )
    op.drop_table("payment_methods")

    op.drop_index(
        "ix_billing_settings_stripe_customer_id",
        table_name="billing_settings",
    )
    op.drop_index(
        "ix_billing_settings_organization_id",
        table_name="billing_settings",
    )
    op.drop_table("billing_settings")
