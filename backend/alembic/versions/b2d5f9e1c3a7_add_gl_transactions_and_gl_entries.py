"""add gl_transactions and gl_entries (general ledger)

Revision ID: b2d5f9e1c3a7
Revises: a1c4e8f9b2d3
Create Date: 2026-09-20

Creates the two core General Ledger tables:

  gl_transactions — one row per financial event (parent)
  gl_entries      — one row per debit or credit line (children)
"""
from alembic import op
import sqlalchemy as sa


revision = "b2d5f9e1c3a7"
down_revision = "a1c4e8f9b2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # gl_transactions
    op.create_table(
        "gl_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("transaction_date", sa.Date(), nullable=False, index=True),
        sa.Column(
            "posted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("transaction_type", sa.String(length=40), nullable=False, index=True),
        sa.Column("reference_number", sa.String(length=40), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True, index=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_reversed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "reversal_of_id",
            sa.Integer(),
            sa.ForeignKey("gl_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_gl_transactions_org_date",
        "gl_transactions",
        ["organization_id", "transaction_date"],
    )
    op.create_index(
        "ix_gl_transactions_source",
        "gl_transactions",
        ["organization_id", "source_type", "source_id"],
    )

    # gl_entries
    op.create_table(
        "gl_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("gl_transactions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "unit_id",
            sa.Integer(),
            sa.ForeignKey("units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("debit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_gl_entries_org_account",
        "gl_entries",
        ["organization_id", "gl_account_id"],
    )
    op.create_index(
        "ix_gl_entries_org_property",
        "gl_entries",
        ["organization_id", "property_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_gl_entries_org_property", table_name="gl_entries")
    op.drop_index("ix_gl_entries_org_account", table_name="gl_entries")
    op.drop_table("gl_entries")

    op.drop_index("ix_gl_transactions_source", table_name="gl_transactions")
    op.drop_index("ix_gl_transactions_org_date", table_name="gl_transactions")
    op.drop_table("gl_transactions")