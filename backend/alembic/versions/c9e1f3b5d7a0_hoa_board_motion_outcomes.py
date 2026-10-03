"""Explicit authorized board motion outcome from an adopted voting threshold.

Revision ID: c9e1f3b5d7a0
Revises: b8d0f2a4c6e9
"""
from alembic import op
import sqlalchemy as sa

revision = "c9e1f3b5d7a0"
down_revision = "b8d0f2a4c6e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_board_motion_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id"), nullable=False),
        sa.Column("motion_draft_id", sa.Integer(), sa.ForeignKey("hoa_motion_drafts.id"), nullable=False, unique=True),
        sa.Column("motion_sha256", sa.String(64), nullable=False),
        sa.Column("rule_adoption_id", sa.Integer(), sa.ForeignKey("hoa_board_rule_adoptions.id"), nullable=False),
        sa.Column("vote_register_sha256", sa.String(64), nullable=False),
        sa.Column("quorum_min", sa.Integer(), nullable=False),
        sa.Column("approval_min", sa.Integer(), nullable=False),
        sa.Column("votes_for", sa.Integer(), nullable=False),
        sa.Column("votes_against", sa.Integer(), nullable=False),
        sa.Column("votes_abstain", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("recorded_by_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_motion_outcome_scope", "hoa_board_motion_outcomes",
                    ["organization_id", "association_id", "property_id", "meeting_draft_id"])


def downgrade():
    op.drop_index("ix_hoa_motion_outcome_scope", table_name="hoa_board_motion_outcomes")
    op.drop_table("hoa_board_motion_outcomes")
