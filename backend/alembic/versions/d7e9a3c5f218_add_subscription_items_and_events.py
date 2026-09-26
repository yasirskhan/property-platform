"""add subscription items and event history

Revision ID: d7e9a3c5f218
Revises: c5a8e2f14b76
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "d7e9a3c5f218"
down_revision = "c5a8e2f14b76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column(
            "quantity",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("unit_price_cents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 1",
            name="ck_subscription_items_quantity",
        ),
        sa.CheckConstraint(
            "unit_price_cents IS NULL OR unit_price_cents >= 0",
            name="ck_subscription_items_unit_price",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["modules.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "module_id",
            name="uq_subscription_items_subscription_module",
        ),
    )
    op.create_index(
        "ix_subscription_items_module_id",
        "subscription_items",
        ["module_id"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_items_subscription_id",
        "subscription_items",
        ["subscription_id"],
        unique=False,
    )

    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscription_events_created_at",
        "subscription_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_events_event_type",
        "subscription_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_events_provider",
        "subscription_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_events_provider_event_id",
        "subscription_events",
        ["provider_event_id"],
        unique=True,
    )
    op.create_index(
        "ix_subscription_events_subscription_id",
        "subscription_events",
        ["subscription_id"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_subscription_event_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'subscription_events is append-only; UPDATE and DELETE are forbidden';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER subscription_events_immutable
            BEFORE UPDATE OR DELETE ON subscription_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_subscription_event_mutation()
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS subscription_events_immutable "
            "ON subscription_events"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS prevent_subscription_event_mutation()"
        )

    op.drop_index(
        "ix_subscription_events_subscription_id",
        table_name="subscription_events",
    )
    op.drop_index(
        "ix_subscription_events_provider_event_id",
        table_name="subscription_events",
    )
    op.drop_index(
        "ix_subscription_events_provider",
        table_name="subscription_events",
    )
    op.drop_index(
        "ix_subscription_events_event_type",
        table_name="subscription_events",
    )
    op.drop_index(
        "ix_subscription_events_created_at",
        table_name="subscription_events",
    )
    op.drop_table("subscription_events")

    op.drop_index(
        "ix_subscription_items_subscription_id",
        table_name="subscription_items",
    )
    op.drop_index(
        "ix_subscription_items_module_id",
        table_name="subscription_items",
    )
    op.drop_table("subscription_items")
