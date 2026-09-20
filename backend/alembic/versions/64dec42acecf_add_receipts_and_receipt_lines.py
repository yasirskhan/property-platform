# ============================================================
# 64dec42acecf_add_receipts_and_receipt_lines.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Creates two tables:
#   receipts       - money coming IN (tenant / owner / other)
#   receipt_lines  - the individual GL breakdown per receipt
#
# Revision ID: 64dec42acecf
# Revises:     b2d5f9e1c3a7  (General Ledger head)
# ============================================================

"""add receipts and receipt lines

Revision ID: 64dec42acecf
Revises: b2d5f9e1c3a7
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "64dec42acecf"
down_revision = "b2d5f9e1c3a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # Table 1: receipts
    # ---------------------------------------------------------
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "cash_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tenant_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "income_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("payer_name", sa.String(length=200), nullable=True),
        sa.Column("received_from", sa.String(length=200), nullable=True),
        sa.Column(
            "exclude_from_mgmt_fee",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "unit_id",
            sa.Integer(),
            sa.ForeignKey("units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reference_number", sa.String(length=60), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "gl_transaction_id",
            sa.Integer(),
            sa.ForeignKey("gl_transactions.id", ondelete="SET NULL"),
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
            sa.ForeignKey("receipts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_receipts_organization_id", "receipts", ["organization_id"]
    )
    op.create_index("ix_receipts_type", "receipts", ["type"])
    op.create_index(
        "ix_receipts_receipt_date", "receipts", ["receipt_date"]
    )
    op.create_index(
        "ix_receipts_cash_gl_account_id", "receipts", ["cash_gl_account_id"]
    )
    op.create_index(
        "ix_receipts_tenant_user_id", "receipts", ["tenant_user_id"]
    )
    op.create_index(
        "ix_receipts_owner_user_id", "receipts", ["owner_user_id"]
    )
    op.create_index(
        "ix_receipts_income_gl_account_id",
        "receipts",
        ["income_gl_account_id"],
    )
    op.create_index(
        "ix_receipts_property_id", "receipts", ["property_id"]
    )
    op.create_index("ix_receipts_unit_id", "receipts", ["unit_id"])
    op.create_index(
        "ix_receipts_gl_transaction_id", "receipts", ["gl_transaction_id"]
    )
    op.create_index(
        "ix_receipts_is_active", "receipts", ["is_active"]
    )

    # ---------------------------------------------------------
    # Table 2: receipt_lines
    # ---------------------------------------------------------
    op.create_table(
        "receipt_lines",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "receipt_id",
            sa.Integer(),
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "unit_id",
            sa.Integer(),
            sa.ForeignKey("units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "amount_to_pay",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("line_date", sa.Date(), nullable=True),
        sa.Column(
            "is_prepayment",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_receipt_lines_organization_id",
        "receipt_lines",
        ["organization_id"],
    )
    op.create_index(
        "ix_receipt_lines_receipt_id", "receipt_lines", ["receipt_id"]
    )
    op.create_index(
        "ix_receipt_lines_gl_account_id",
        "receipt_lines",
        ["gl_account_id"],
    )
    op.create_index(
        "ix_receipt_lines_property_id", "receipt_lines", ["property_id"]
    )
    op.create_index(
        "ix_receipt_lines_unit_id", "receipt_lines", ["unit_id"]
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_receipt_lines_unit_id", table_name="receipt_lines")
    op.drop_index("ix_receipt_lines_property_id", table_name="receipt_lines")
    op.drop_index("ix_receipt_lines_gl_account_id", table_name="receipt_lines")
    op.drop_index("ix_receipt_lines_receipt_id", table_name="receipt_lines")
    op.drop_index(
        "ix_receipt_lines_organization_id", table_name="receipt_lines"
    )
    op.drop_table("receipt_lines")

    op.drop_index("ix_receipts_is_active", table_name="receipts")
    op.drop_index("ix_receipts_gl_transaction_id", table_name="receipts")
    op.drop_index("ix_receipts_unit_id", table_name="receipts")
    op.drop_index("ix_receipts_property_id", table_name="receipts")
    op.drop_index(
        "ix_receipts_income_gl_account_id", table_name="receipts"
    )
    op.drop_index("ix_receipts_owner_user_id", table_name="receipts")
    op.drop_index("ix_receipts_tenant_user_id", table_name="receipts")
    op.drop_index(
        "ix_receipts_cash_gl_account_id", table_name="receipts"
    )
    op.drop_index("ix_receipts_receipt_date", table_name="receipts")
    op.drop_index("ix_receipts_type", table_name="receipts")
    op.drop_index("ix_receipts_organization_id", table_name="receipts")
    op.drop_table("receipts")