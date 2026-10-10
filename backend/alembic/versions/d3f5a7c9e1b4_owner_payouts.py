"""owner payout drafts

Revision ID: d3f5a7c9e1b4
Revises: c1e3a5d7f9b2
"""
from alembic import op
import sqlalchemy as sa

revision = "d3f5a7c9e1b4"
down_revision = "c1e3a5d7f9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_payouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("batch_reference", sa.String(length=50), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("destination_last4", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("gl_transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["gl_transaction_id"], ["gl_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "organization_id",
            "batch_reference",
            "owner_id",
            name="uq_owner_payout_org_batch_owner",
        ),
    )
    op.create_index("ix_owner_payouts_organization_id", "owner_payouts", ["organization_id"])
    op.create_index("ix_owner_payouts_batch_reference", "owner_payouts", ["batch_reference"])
    op.create_index("ix_owner_payouts_owner_id", "owner_payouts", ["owner_id"])
    op.create_index("ix_owner_payouts_bank_account_id", "owner_payouts", ["bank_account_id"])
    op.create_index("ix_owner_payouts_effective_date", "owner_payouts", ["effective_date"])
    op.create_index("ix_owner_payouts_status", "owner_payouts", ["status"])
    op.create_index("ix_owner_payouts_gl_transaction_id", "owner_payouts", ["gl_transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_owner_payouts_gl_transaction_id", table_name="owner_payouts")
    op.drop_index("ix_owner_payouts_status", table_name="owner_payouts")
    op.drop_index("ix_owner_payouts_effective_date", table_name="owner_payouts")
    op.drop_index("ix_owner_payouts_bank_account_id", table_name="owner_payouts")
    op.drop_index("ix_owner_payouts_owner_id", table_name="owner_payouts")
    op.drop_index("ix_owner_payouts_batch_reference", table_name="owner_payouts")
    op.drop_index("ix_owner_payouts_organization_id", table_name="owner_payouts")
    op.drop_table("owner_payouts")
