"""Staff-only assessment proposals, no financial obligations or posting.

Revision ID: f8b0c2d4e6a9
Revises: e7a9b1c3d5f8
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "f8b0c2d4e6a9"
down_revision = "e7a9b1c3d5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_assessment_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("assessment_type", sa.String(12), nullable=False),
        sa.Column("frequency", sa.String(12), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("proposed_first_on", sa.Date(), nullable=False),
        sa.Column("proposed_through", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_assessment_proposals_id", "hoa_assessment_proposals", ["id"])
    op.create_index("ix_hoa_assessment_proposals_organization_id", "hoa_assessment_proposals", ["organization_id"])
    op.create_index("ix_hoa_assessment_proposals_association_id", "hoa_assessment_proposals", ["association_id"])
    op.create_index("ix_hoa_assessment_proposals_property_id", "hoa_assessment_proposals", ["property_id"])
    op.create_index("ix_hoa_proposal_scope", "hoa_assessment_proposals", ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_proposal_scope", table_name="hoa_assessment_proposals")
    op.drop_index("ix_hoa_assessment_proposals_property_id", table_name="hoa_assessment_proposals")
    op.drop_index("ix_hoa_assessment_proposals_association_id", table_name="hoa_assessment_proposals")
    op.drop_index("ix_hoa_assessment_proposals_organization_id", table_name="hoa_assessment_proposals")
    op.drop_index("ix_hoa_assessment_proposals_id", table_name="hoa_assessment_proposals")
    op.drop_table("hoa_assessment_proposals")
