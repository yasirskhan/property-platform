"""Staff HOA meeting plan records only; no official minutes, votes or authority.

Revision ID: d8f0a2b4c6e9
Revises: c7e9a1b3d5f2
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "d8f0a2b4c6e9"
down_revision = "c7e9a1b3d5f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_meeting_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("proposed_on", sa.Date(), nullable=False),
        sa.Column("staff_agenda", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_meeting_drafts_id", "hoa_meeting_drafts", ["id"])
    op.create_index("ix_hoa_meeting_drafts_organization_id", "hoa_meeting_drafts", ["organization_id"])
    op.create_index("ix_hoa_meeting_drafts_association_id", "hoa_meeting_drafts", ["association_id"])
    op.create_index("ix_hoa_meeting_drafts_property_id", "hoa_meeting_drafts", ["property_id"])
    op.create_index("ix_hoa_meeting_draft_scope", "hoa_meeting_drafts", ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_meeting_draft_scope", table_name="hoa_meeting_drafts")
    op.drop_index("ix_hoa_meeting_drafts_property_id", table_name="hoa_meeting_drafts")
    op.drop_index("ix_hoa_meeting_drafts_association_id", table_name="hoa_meeting_drafts")
    op.drop_index("ix_hoa_meeting_drafts_organization_id", table_name="hoa_meeting_drafts")
    op.drop_index("ix_hoa_meeting_drafts_id", table_name="hoa_meeting_drafts")
    op.drop_table("hoa_meeting_drafts")
