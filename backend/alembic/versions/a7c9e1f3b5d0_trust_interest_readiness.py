"""Trust-account interest manual policy review readiness, no financial transactions.

Revision ID: a7c9e1f3b5d0
Revises: f6e8a0c2d4e5
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c9e1f3b5d0"
down_revision = "f6e8a0c2d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trust_interest_readiness",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jurisdiction", sa.String(80), nullable=True),
        sa.Column("proposed_recipient", sa.String(24), nullable=False),
        sa.Column("basis_reference", sa.String(200), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "bank_account_id", name="uq_trust_interest_org_bank"),
    )
    op.create_index("ix_trust_interest_readiness_organization_id", "trust_interest_readiness", ["organization_id"])
    op.create_index("ix_trust_interest_readiness_bank_account_id", "trust_interest_readiness", ["bank_account_id"])


def downgrade():
    op.drop_index("ix_trust_interest_readiness_bank_account_id", table_name="trust_interest_readiness")
    op.drop_index("ix_trust_interest_readiness_organization_id", table_name="trust_interest_readiness")
    op.drop_table("trust_interest_readiness")
