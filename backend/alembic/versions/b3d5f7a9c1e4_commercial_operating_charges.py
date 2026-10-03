"""Operational Commercial CAM/NNN tenant charge records.

Revision ID: b3d5f7a9c1e4
Revises: a2c4e6f8b0d1
"""
from alembic import op
import sqlalchemy as sa

revision = "b3d5f7a9c1e4"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commercial_operating_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lease_id", sa.Integer(), sa.ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("abstract_id", sa.Integer(), sa.ForeignKey("commercial_lease_abstracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("terms_id", sa.Integer(), sa.ForeignKey("commercial_lease_terms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("posting_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("cam_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("insurance_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("receivable_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("income_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("charge_id", sa.Integer(), sa.ForeignKey("charges.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("gl_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("reversal_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("request_key", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="POSTED"),
        sa.Column("reversal_on", sa.Date(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_commercial_operating_charge_request"),
    )
    op.create_index("ix_commercial_operating_charge_org", "commercial_operating_charges", ["organization_id"])
    op.create_index("ix_commercial_operating_charge_property", "commercial_operating_charges", ["property_id"])
    op.create_index("ix_commercial_operating_charge_unit", "commercial_operating_charges", ["unit_id"])
    op.create_index("ix_commercial_operating_charge_lease", "commercial_operating_charges", ["lease_id"])
    op.create_index("ix_commercial_operating_charge_abstract", "commercial_operating_charges", ["abstract_id"])
    op.create_index("ix_commercial_operating_charge_terms", "commercial_operating_charges", ["terms_id"])
    op.create_index("ix_commercial_operating_charge_tenant", "commercial_operating_charges", ["tenant_user_id"])
    op.create_index("ix_commercial_operating_charge_scope", "commercial_operating_charges",
                    ["organization_id", "property_id", "lease_id", "status"])


def downgrade():
    op.drop_table("commercial_operating_charges")
