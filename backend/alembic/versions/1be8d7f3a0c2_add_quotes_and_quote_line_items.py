"""add quotes and quote line items

Revision ID: 1be8d7f3a0c2
Revises: 0ad7c6e2f9b1
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "1be8d7f3a0c2"
down_revision = "0ad7c6e2f9b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="DRAFT", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("discount_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("subtotal_cents >= 0", name="ck_quotes_subtotal"),
        sa.CheckConstraint("discount_cents >= 0", name="ck_quotes_discount"),
        sa.CheckConstraint("total_cents >= 0", name="ck_quotes_total"),
        sa.CheckConstraint(
            "status IN ('DRAFT','SENT','ACCEPTED','EXPIRED','CANCELLED')",
            name="ck_quotes_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotes_organization_id", "quotes", ["organization_id"], unique=False)
    op.create_index("ix_quotes_status", "quotes", ["status"], unique=False)

    op.create_table(
        "quote_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=True),
        sa.Column("add_on_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("line_total_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity >= 1", name="ck_quote_line_items_quantity"),
        sa.CheckConstraint("unit_price_cents >= 0", name="ck_quote_line_items_unit_price"),
        sa.CheckConstraint("line_total_cents >= 0", name="ck_quote_line_items_total"),
        sa.CheckConstraint(
            "NOT (module_id IS NOT NULL AND add_on_id IS NOT NULL)",
            name="ck_quote_line_items_single_catalog_ref",
        ),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["add_on_id"], ["add_ons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_line_items_quote_id", "quote_line_items", ["quote_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_quote_line_items_quote_id", table_name="quote_line_items")
    op.drop_table("quote_line_items")
    op.drop_index("ix_quotes_status", table_name="quotes")
    op.drop_index("ix_quotes_organization_id", table_name="quotes")
    op.drop_table("quotes")
