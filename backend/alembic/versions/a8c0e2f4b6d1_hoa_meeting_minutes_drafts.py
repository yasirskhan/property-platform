"""Add scoped staff minutes drafts. No legal certification.

Revision ID: a8c0e2f4b6d1
Revises: f7b9d1e3a5c2
"""
from alembic import op
import sqlalchemy as sa

revision = "a8c0e2f4b6d1"
down_revision = "f7b9d1e3a5c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_meeting_minutes_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_minutes", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("meeting_draft_id", name="uq_hoa_minutes_per_meeting"),
    )
    for field in ("organization_id", "association_id", "property_id", "meeting_draft_id"):
        op.create_index(f"ix_hoa_minutes_{field}", "hoa_meeting_minutes_drafts", [field])
    op.create_index("ix_hoa_minutes_scope", "hoa_meeting_minutes_drafts",
                    ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_minutes_scope", table_name="hoa_meeting_minutes_drafts")
    for field in ("meeting_draft_id", "property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_minutes_{field}", table_name="hoa_meeting_minutes_drafts")
    op.drop_table("hoa_meeting_minutes_drafts")
