"""Authenticated immutable individual HOA board votes.

Revision ID: a7c9e1f3b5d8
Revises: f6b8d0e2a4c7
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c9e1f3b5d8"
down_revision = "f6b8d0e2a4c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_board_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id"), nullable=False),
        sa.Column("motion_draft_id", sa.Integer(), sa.ForeignKey("hoa_motion_drafts.id"), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("voter_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("motion_sha256", sa.String(length=64), nullable=False),
        sa.Column("choice", sa.String(length=12), nullable=False),
        sa.Column("voted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("motion_draft_id", "board_seat_id",
                            name="uq_hoa_board_vote_motion_seat"),
    )
    op.create_index(
        "ix_hoa_board_vote_scope", "hoa_board_votes",
        ["organization_id", "association_id", "property_id", "meeting_draft_id"],
    )


def downgrade():
    op.drop_index("ix_hoa_board_vote_scope", table_name="hoa_board_votes")
    op.drop_table("hoa_board_votes")
