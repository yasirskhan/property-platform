"""add per-bank check setup
Revision ID: f2a4c6e8b0d5
Revises: d8e0f2a4b6c3
"""
from alembic import op
import sqlalchemy as sa
revision = "f2a4c6e8b0d5"
down_revision = "d8e0f2a4b6c3"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "bank_check_setups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=False),
        sa.Column("next_check_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("check_number_prefix", sa.String(length=20), nullable=True),
        sa.Column("check_stock_position", sa.String(length=10), nullable=False, server_default="TOP"),
        sa.Column("memo_line_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("signature_line_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "bank_account_id", name="uq_bank_check_setup_org_bank"),
        sa.UniqueConstraint("bank_account_id", name="uq_bank_check_setups_bank_account_id"),
    )
    op.create_index("ix_bank_check_setups_organization_id", "bank_check_setups", ["organization_id"])
    op.create_index("ix_bank_check_setups_bank_account_id", "bank_check_setups", ["bank_account_id"], unique=True)

def downgrade():
    op.drop_index("ix_bank_check_setups_bank_account_id", table_name="bank_check_setups")
    op.drop_index("ix_bank_check_setups_organization_id", table_name="bank_check_setups")
    op.drop_table("bank_check_setups")
