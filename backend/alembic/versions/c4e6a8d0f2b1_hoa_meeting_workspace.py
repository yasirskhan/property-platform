"""HOA staff meeting participation and nonbinding motion drafts.

Revision ID: c4e6a8d0f2b1
Revises: c3e5a7b9d1f2
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c4e6a8d0f2b1"
down_revision = "c3e5a7b9d1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_meeting_participation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_attendance", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("meeting_draft_id", "contact_link_id", name="uq_hoa_meeting_participation_contact"),
    )
    for name in ("id", "organization_id", "association_id", "property_id", "meeting_draft_id", "contact_link_id"):
        op.create_index(f"ix_hoa_meeting_participation_{name}", "hoa_meeting_participation", [name])
    op.create_index("ix_hoa_participation_scope", "hoa_meeting_participation",
                    ["organization_id", "association_id", "property_id"])

    op.create_table(
        "hoa_motion_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_motion", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for name in ("id", "organization_id", "association_id", "property_id", "meeting_draft_id"):
        op.create_index(f"ix_hoa_motion_drafts_{name}", "hoa_motion_drafts", [name])
    op.create_index("ix_hoa_motion_scope", "hoa_motion_drafts",
                    ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_motion_scope", table_name="hoa_motion_drafts")
    for name in ("meeting_draft_id", "property_id", "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_motion_drafts_{name}", table_name="hoa_motion_drafts")
    op.drop_table("hoa_motion_drafts")
    op.drop_index("ix_hoa_participation_scope", table_name="hoa_meeting_participation")
    for name in ("contact_link_id", "meeting_draft_id", "property_id", "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_meeting_participation_{name}", table_name="hoa_meeting_participation")
    op.drop_table("hoa_meeting_participation")
