"""Annual Commercial CAM reconciliation records.

Revision ID: c4e6f8a0b2d5
Revises: b3d5f7a9c1e4
"""
from alembic import op
import sqlalchemy as sa

revision = "c4e6f8a0b2d5"
down_revision = "b3d5f7a9c1e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commercial_cam_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lease_id", sa.Integer(), sa.ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("abstract_id", sa.Integer(), sa.ForeignKey("commercial_lease_abstracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("terms_id", sa.Integer(), sa.ForeignKey("commercial_lease_terms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reconciliation_year", sa.Integer(), nullable=False),
        sa.Column("actual_cam_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("share_percent", sa.Numeric(7, 4), nullable=False),
        sa.Column("actual_tenant_share", sa.Numeric(14, 2), nullable=False),
        sa.Column("estimated_cam_billed", sa.Numeric(14, 2), nullable=False),
        sa.Column("true_up_amount", sa.Numeric(14, 2), nullable=False),
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
        sa.UniqueConstraint("organization_id", "request_key", name="uq_commercial_cam_recon_request"),
        sa.UniqueConstraint("abstract_id", "reconciliation_year", name="uq_commercial_cam_recon_abstract_year"),
    )
    op.create_index("ix_commercial_cam_recon_org", "commercial_cam_reconciliations", ["organization_id"])
    op.create_index("ix_commercial_cam_recon_property", "commercial_cam_reconciliations", ["property_id"])
    op.create_index("ix_commercial_cam_recon_lease", "commercial_cam_reconciliations", ["lease_id"])
    op.create_index("ix_commercial_cam_recon_abstract", "commercial_cam_reconciliations", ["abstract_id"])
    op.create_index("ix_commercial_cam_recon_terms", "commercial_cam_reconciliations", ["terms_id"])
    op.create_index("ix_commercial_cam_recon_tenant", "commercial_cam_reconciliations", ["tenant_user_id"])
    op.create_index("ix_commercial_cam_recon_evidence", "commercial_cam_reconciliations", ["evidence_attachment_id"])
    op.create_index("ix_commercial_cam_recon_scope", "commercial_cam_reconciliations",
                    ["organization_id", "property_id", "lease_id", "reconciliation_year"])


def downgrade():
    op.drop_table("commercial_cam_reconciliations")
