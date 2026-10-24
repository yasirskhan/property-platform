"""Immutable authorized board adoption of exact staff minutes revision.

Revision ID: f6b8d0e2a4c7
Revises: e5a7c9d1f3b6
"""
from alembic import op
import sqlalchemy as sa

revision = "f6b8d0e2a4c7"
down_revision = "e5a7c9d1f3b6"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("hoa_meeting_minutes_drafts", sa.Column(
        "revision", sa.Integer(), nullable=False, server_default="1",
    ))
    op.create_table(
        "hoa_meeting_minutes_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id"), nullable=False),
        sa.Column("minutes_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_minutes_drafts.id"), nullable=False, unique=True),
        sa.Column("minutes_revision", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approval_note", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_hoa_minutes_approval_scope", "hoa_meeting_minutes_approvals",
        ["organization_id", "association_id", "property_id", "meeting_draft_id"],
    )

def downgrade():
    op.drop_index("ix_hoa_minutes_approval_scope", table_name="hoa_meeting_minutes_approvals")
    op.drop_table("hoa_meeting_minutes_approvals")
    op.drop_column("hoa_meeting_minutes_drafts", "revision")
