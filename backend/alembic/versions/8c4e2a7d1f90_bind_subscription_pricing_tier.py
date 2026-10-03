"""bind subscriptions to purchased pricing tiers

Revision ID: 8c4e2a7d1f90
Revises: 3b8d1f5c7a20
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "8c4e2a7d1f90"
down_revision = "3b8d1f5c7a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(
            sa.Column("pricing_tier_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_subscriptions_pricing_tier_id",
            "pricing_tiers",
            ["pricing_tier_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_subscriptions_pricing_tier_id",
            ["pricing_tier_id"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE subscriptions
            SET pricing_tier_id = (
                SELECT billing_checkout_sessions.pricing_tier_id
                FROM billing_checkout_sessions
                WHERE
                    billing_checkout_sessions.organization_id =
                        subscriptions.organization_id
                    AND billing_checkout_sessions.status = 'COMPLETED'
                ORDER BY
                    billing_checkout_sessions.updated_at DESC,
                    billing_checkout_sessions.id DESC
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1
                FROM billing_checkout_sessions
                WHERE
                    billing_checkout_sessions.organization_id =
                        subscriptions.organization_id
                    AND billing_checkout_sessions.status = 'COMPLETED'
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_index("ix_subscriptions_pricing_tier_id")
        batch_op.drop_constraint(
            "fk_subscriptions_pricing_tier_id",
            type_="foreignkey",
        )
        batch_op.drop_column("pricing_tier_id")
