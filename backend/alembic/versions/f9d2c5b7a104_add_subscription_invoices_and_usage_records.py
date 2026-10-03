"""add subscription invoices and usage records

Revision ID: f9d2c5b7a104
Revises: e8c1b4a6d903
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "f9d2c5b7a104"
down_revision = "e8c1b4a6d903"
branch_labels = None
depends_on = None

invoice_status = sa.Enum(
    "DRAFT",
    "OPEN",
    "PAID",
    "VOID",
    "UNCOLLECTIBLE",
    name="subscription_invoice_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "subscription_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("provider_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            invoice_status,
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column(
            "subtotal_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "discount_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "tax_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "amount_paid_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "amount_due_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(), nullable=True),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "subtotal_cents >= 0",
            name="ck_subscription_invoices_subtotal",
        ),
        sa.CheckConstraint(
            "discount_cents >= 0",
            name="ck_subscription_invoices_discount",
        ),
        sa.CheckConstraint(
            "tax_cents >= 0",
            name="ck_subscription_invoices_tax",
        ),
        sa.CheckConstraint(
            "total_cents >= 0",
            name="ck_subscription_invoices_total",
        ),
        sa.CheckConstraint(
            "amount_paid_cents >= 0",
            name="ck_subscription_invoices_paid",
        ),
        sa.CheckConstraint(
            "amount_due_cents >= 0",
            name="ck_subscription_invoices_due",
        ),
        sa.CheckConstraint(
            "period_end IS NULL OR period_start IS NULL "
            "OR period_end >= period_start",
            name="ck_subscription_invoices_period_range",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscription_invoices_subscription_id",
        "subscription_invoices",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_invoices_provider_invoice_id",
        "subscription_invoices",
        ["provider_invoice_id"],
        unique=True,
    )
    op.create_index(
        "ix_subscription_invoices_invoice_number",
        "subscription_invoices",
        ["invoice_number"],
        unique=False,
    )
    op.create_index(
        "ix_subscription_invoices_status",
        "subscription_invoices",
        ["status"],
        unique=False,
    )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("subscription_item_id", sa.Integer(), nullable=True),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("usage_at", sa.DateTime(), nullable=False),
        sa.Column("provider_usage_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_usage_records_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_item_id"],
            ["subscription_items.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_records_subscription_id",
        "usage_records",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        "ix_usage_records_subscription_item_id",
        "usage_records",
        ["subscription_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_usage_records_metric_key",
        "usage_records",
        ["metric_key"],
        unique=False,
    )
    op.create_index(
        "ix_usage_records_usage_at",
        "usage_records",
        ["usage_at"],
        unique=False,
    )
    op.create_index(
        "ix_usage_records_provider_usage_id",
        "usage_records",
        ["provider_usage_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_usage_records_provider_usage_id",
        table_name="usage_records",
    )
    op.drop_index("ix_usage_records_usage_at", table_name="usage_records")
    op.drop_index("ix_usage_records_metric_key", table_name="usage_records")
    op.drop_index(
        "ix_usage_records_subscription_item_id",
        table_name="usage_records",
    )
    op.drop_index(
        "ix_usage_records_subscription_id",
        table_name="usage_records",
    )
    op.drop_table("usage_records")

    op.drop_index(
        "ix_subscription_invoices_status",
        table_name="subscription_invoices",
    )
    op.drop_index(
        "ix_subscription_invoices_invoice_number",
        table_name="subscription_invoices",
    )
    op.drop_index(
        "ix_subscription_invoices_provider_invoice_id",
        table_name="subscription_invoices",
    )
    op.drop_index(
        "ix_subscription_invoices_subscription_id",
        table_name="subscription_invoices",
    )
    op.drop_table("subscription_invoices")
