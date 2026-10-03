"""Versioned source-linked commercial lease term abstracts.

Revision ID: a2c4e6f8b0d1
Revises: f5a7c9e1b3d8
"""
from alembic import op
import sqlalchemy as sa

revision = "a2c4e6f8b0d1"
down_revision = "f5a7c9e1b3d8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commercial_lease_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lease_id", sa.Integer(), sa.ForeignKey("leases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("abstract_id", sa.Integer(), sa.ForeignKey("commercial_lease_abstracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("base_rent_monthly", sa.Numeric(14, 2)),
        sa.Column("cam_estimate_monthly", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("property_tax_estimate_monthly", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("insurance_estimate_monthly", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("cam_share_percent", sa.Numeric(7, 4)),
        sa.Column("percentage_rent_rate", sa.Numeric(7, 4)),
        sa.Column("percentage_rent_breakpoint_annual", sa.Numeric(14, 2)),
        sa.Column("ti_allowance_total", sa.Numeric(14, 2)),
        sa.Column("co_tenancy_summary", sa.Text()),
        sa.Column("billing_authorized_at", sa.DateTime()),
        sa.Column("billing_authorized_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("billing_authorization_note", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("abstract_id", "revision", name="uq_commercial_terms_abstract_revision"),
    )
    op.create_index("ix_commercial_terms_org", "commercial_lease_terms", ["organization_id"])
    op.create_index("ix_commercial_terms_property", "commercial_lease_terms", ["property_id"])
    op.create_index("ix_commercial_terms_lease", "commercial_lease_terms", ["lease_id"])
    op.create_index("ix_commercial_terms_abstract", "commercial_lease_terms", ["abstract_id"])
    op.create_index("ix_commercial_terms_source", "commercial_lease_terms", ["source_attachment_id"])
    op.create_index("ix_commercial_terms_scope", "commercial_lease_terms",
                    ["organization_id", "property_id", "lease_id", "is_active"])

    op.create_table(
        "commercial_rent_escalations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_id", sa.Integer(), sa.ForeignKey("commercial_lease_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("monthly_base_rent", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("terms_id", "starts_on", name="uq_commercial_escalation_terms_start"),
    )
    op.create_index("ix_commercial_escalation_org", "commercial_rent_escalations", ["organization_id"])
    op.create_index("ix_commercial_escalation_terms", "commercial_rent_escalations", ["terms_id"])

    op.create_table(
        "commercial_lease_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_id", sa.Integer(), sa.ForeignKey("commercial_lease_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_type", sa.String(24), nullable=False),
        sa.Column("exercise_start_on", sa.Date()),
        sa.Column("exercise_end_on", sa.Date()),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_commercial_option_org", "commercial_lease_options", ["organization_id"])
    op.create_index("ix_commercial_option_terms", "commercial_lease_options", ["terms_id", "option_type"])


def downgrade():
    op.drop_table("commercial_lease_options")
    op.drop_table("commercial_rent_escalations")
    op.drop_table("commercial_lease_terms")
