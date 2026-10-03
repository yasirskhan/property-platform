"""Final Phase 4.8 Commercial percentage-rent and TI utilization records.

Revision ID: d5f7a9c1e3b6
Revises: c4e6f8a0b2d5
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f7a9c1e3b6"
down_revision = "c4e6f8a0b2d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commercial_percentage_rent_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lease_id", sa.Integer(), sa.ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("abstract_id", sa.Integer(), sa.ForeignKey("commercial_lease_abstracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("terms_id", sa.Integer(), sa.ForeignKey("commercial_lease_terms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reporting_year", sa.Integer(), nullable=False),
        sa.Column("gross_sales", sa.Numeric(16, 2), nullable=False),
        sa.Column("breakpoint_annual", sa.Numeric(14, 2), nullable=False),
        sa.Column("rate_percent", sa.Numeric(7, 4), nullable=False),
        sa.Column("excess_sales", sa.Numeric(16, 2), nullable=False),
        sa.Column("percentage_rent_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("posting_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("receivable_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("income_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("charge_id", sa.Integer(), sa.ForeignKey("charges.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("gl_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("reversal_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("request_key", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reversal_on", sa.Date(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_commercial_pct_rent_request"),
        sa.UniqueConstraint("abstract_id", "reporting_year", name="uq_commercial_pct_rent_abstract_year"),
    )
    for name, cols in (
        ("ix_commercial_pct_rent_org", ["organization_id"]),
        ("ix_commercial_pct_rent_property", ["property_id"]),
        ("ix_commercial_pct_rent_lease", ["lease_id"]),
        ("ix_commercial_pct_rent_abstract", ["abstract_id"]),
        ("ix_commercial_pct_rent_terms", ["terms_id"]),
        ("ix_commercial_pct_rent_tenant", ["tenant_user_id"]),
        ("ix_commercial_pct_rent_evidence", ["evidence_attachment_id"]),
        ("ix_commercial_pct_rent_scope", ["organization_id", "property_id", "lease_id", "reporting_year"]),
    ):
        op.create_index(name, "commercial_percentage_rent_charges", cols)

    op.create_table(
        "commercial_ti_allowance_uses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lease_id", sa.Integer(), sa.ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("abstract_id", sa.Integer(), sa.ForeignKey("commercial_lease_abstracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("terms_id", sa.Integer(), sa.ForeignKey("commercial_lease_terms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("allowance_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("remaining_after", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("request_key", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("voided_on", sa.Date(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_commercial_ti_use_request"),
    )
    for name, cols in (
        ("ix_commercial_ti_use_org", ["organization_id"]),
        ("ix_commercial_ti_use_property", ["property_id"]),
        ("ix_commercial_ti_use_lease", ["lease_id"]),
        ("ix_commercial_ti_use_abstract", ["abstract_id"]),
        ("ix_commercial_ti_use_terms", ["terms_id"]),
        ("ix_commercial_ti_use_tenant", ["tenant_user_id"]),
        ("ix_commercial_ti_use_evidence", ["evidence_attachment_id"]),
        ("ix_commercial_ti_use_scope", ["organization_id", "property_id", "lease_id", "status"]),
    ):
        op.create_index(name, "commercial_ti_allowance_uses", cols)


def downgrade():
    op.drop_table("commercial_ti_allowance_uses")
    op.drop_table("commercial_percentage_rent_charges")
