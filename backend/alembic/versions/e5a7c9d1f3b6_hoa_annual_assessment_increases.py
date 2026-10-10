"""Link approved annual budgets to separately approved member assessment increases.

Revision ID: e5a7c9d1f3b6
Revises: d4f6a8c0e2b5
"""
from alembic import op
import sqlalchemy as sa

revision = "e5a7c9d1f3b6"
down_revision = "d4f6a8c0e2b5"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "hoa_annual_assessment_increases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("hoa_annual_budgets.id"), nullable=False),
        sa.Column("source_charge_id", sa.Integer(), sa.ForeignKey("hoa_member_assessment_charges.id"), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("hoa_assessment_proposals.id"), nullable=False, unique=True),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("previous_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("budget_id", "source_charge_id", name="uq_hoa_increase_budget_charge"),
    )
    op.create_index("ix_hoa_increase_scope", "hoa_annual_assessment_increases",
                    ["organization_id", "association_id", "property_id", "budget_id"])

def downgrade():
    op.drop_index("ix_hoa_increase_scope", table_name="hoa_annual_assessment_increases")
    op.drop_table("hoa_annual_assessment_increases")
