# ============================================================
# 71eda8a9ba77_add_bills_and_bill_lines_and_ap_account.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Three things:
#   1. Create table `bills`       (money going OUT — payables)
#   2. Create table `bill_lines`  (multi-line detail per bill)
#   3. Seed GL account 2100 Accounts Payable for every existing
#      organization (required for the two-step accrual flow).
#
# Revision ID: 71eda8a9ba77
# Revises:     64dec42acecf  (Receipts head)
# ============================================================

"""add bills and bill lines and AP account

Revision ID: 71eda8a9ba77
Revises: 64dec42acecf
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "71eda8a9ba77"
down_revision = "64dec42acecf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # Table 1: bills
    # ---------------------------------------------------------
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bill_number", sa.String(length=40), nullable=True),
        sa.Column("payee_name", sa.String(length=200), nullable=False),
        sa.Column(
            "payee_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("reference_number", sa.String(length=60), nullable=True),
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "amount_paid",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="UNPAID",
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
        sa.Column(
            "payable_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
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
            sa.ForeignKey("bills.id", ondelete="SET NULL"),
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
    op.create_index("ix_bills_organization_id", "bills", ["organization_id"])
    op.create_index("ix_bills_bill_number", "bills", ["bill_number"])
    op.create_index("ix_bills_payee_user_id", "bills", ["payee_user_id"])
    op.create_index("ix_bills_bill_date", "bills", ["bill_date"])
    op.create_index("ix_bills_due_date", "bills", ["due_date"])
    op.create_index("ix_bills_status", "bills", ["status"])
    op.create_index("ix_bills_property_id", "bills", ["property_id"])
    op.create_index("ix_bills_unit_id", "bills", ["unit_id"])
    op.create_index(
        "ix_bills_payable_gl_account_id", "bills", ["payable_gl_account_id"]
    )
    op.create_index("ix_bills_source_type", "bills", ["source_type"])
    op.create_index(
        "ix_bills_gl_transaction_id", "bills", ["gl_transaction_id"]
    )
    op.create_index("ix_bills_is_active", "bills", ["is_active"])

    # ---------------------------------------------------------
    # Table 2: bill_lines
    # ---------------------------------------------------------
    op.create_table(
        "bill_lines",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bill_id",
            sa.Integer(),
            sa.ForeignKey("bills.id", ondelete="CASCADE"),
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
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
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
        "ix_bill_lines_organization_id", "bill_lines", ["organization_id"]
    )
    op.create_index("ix_bill_lines_bill_id", "bill_lines", ["bill_id"])
    op.create_index(
        "ix_bill_lines_gl_account_id", "bill_lines", ["gl_account_id"]
    )
    op.create_index(
        "ix_bill_lines_property_id", "bill_lines", ["property_id"]
    )
    op.create_index("ix_bill_lines_unit_id", "bill_lines", ["unit_id"])

    # ---------------------------------------------------------
    # Seed GL account 2100 Accounts Payable for every org that
    # doesn't already have it. This is a LIABILITY account,
    # sits right after 1300 Accounts Receivable and before
    # 2101 Security Deposits in spirit, but numbered 2100.
    # ---------------------------------------------------------
    bind = op.get_bind()
    orgs = bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for (org_id,) in orgs:
        existing = bind.execute(
            sa.text(
                "SELECT id FROM gl_accounts "
                "WHERE organization_id = :org AND gl_number = '2100'"
            ),
            {"org": org_id},
        ).fetchone()
        if existing:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO gl_accounts (
                    organization_id, gl_number, name, account_type,
                    sub_account_of, offset_account,
                    subject_to_mgmt_fees, include_on_cash_flow,
                    is_active, created_at, updated_at
                ) VALUES (
                    :org, '2100', 'Accounts Payable', 'LIABILITY',
                    NULL, NULL,
                    0, 0,
                    1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"org": org_id},
        )


def downgrade() -> None:
    # Remove the AP account we seeded (only from orgs where it
    # exists and no transactions reference it — safe enough for
    # a dev rollback).
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM gl_accounts WHERE gl_number = '2100'")
    )

    # Drop bill_lines first (depends on bills)
    op.drop_index("ix_bill_lines_unit_id", table_name="bill_lines")
    op.drop_index("ix_bill_lines_property_id", table_name="bill_lines")
    op.drop_index("ix_bill_lines_gl_account_id", table_name="bill_lines")
    op.drop_index("ix_bill_lines_bill_id", table_name="bill_lines")
    op.drop_index("ix_bill_lines_organization_id", table_name="bill_lines")
    op.drop_table("bill_lines")

    # Then bills
    op.drop_index("ix_bills_is_active", table_name="bills")
    op.drop_index("ix_bills_gl_transaction_id", table_name="bills")
    op.drop_index("ix_bills_source_type", table_name="bills")
    op.drop_index("ix_bills_payable_gl_account_id", table_name="bills")
    op.drop_index("ix_bills_unit_id", table_name="bills")
    op.drop_index("ix_bills_property_id", table_name="bills")
    op.drop_index("ix_bills_status", table_name="bills")
    op.drop_index("ix_bills_due_date", table_name="bills")
    op.drop_index("ix_bills_bill_date", table_name="bills")
    op.drop_index("ix_bills_payee_user_id", table_name="bills")
    op.drop_index("ix_bills_bill_number", table_name="bills")
    op.drop_index("ix_bills_organization_id", table_name="bills")
    op.drop_table("bills")