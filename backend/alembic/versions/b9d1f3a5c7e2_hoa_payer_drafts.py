"""Staff suggested HOA payer references. Not receivables.

Revision ID: b9d1f3a5c7e2
Revises: a8c0e2f4b6d1
"""
from alembic import op
import sqlalchemy as sa

revision = "b9d1f3a5c7e2"
down_revision = "a8c0e2f4b6d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_payer_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("hoa_assessment_proposals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("proposal_id", name="uq_hoa_payer_draft_proposal"),
    )
    for field in ("organization_id", "association_id", "property_id", "proposal_id", "contact_link_id"):
        op.create_index("ix_hoa_payer_drafts_" + field, "hoa_payer_drafts", [field])
    op.create_index("ix_hoa_payer_scope", "hoa_payer_drafts",
                    ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_payer_scope", table_name="hoa_payer_drafts")
    for field in ("contact_link_id", "proposal_id", "property_id", "association_id", "organization_id"):
        op.drop_index("ix_hoa_payer_drafts_" + field, table_name="hoa_payer_drafts")
    op.drop_table("hoa_payer_drafts")
