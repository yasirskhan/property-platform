"""Authenticated adoption of explicitly configured HOA board thresholds.

Revision ID: b8d0f2a4c6e9
Revises: a7c9e1f3b5d8
"""
from alembic import op
import sqlalchemy as sa

revision = "b8d0f2a4c6e9"
down_revision = "a7c9e1f3b5d8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_board_rule_adoptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("rule_draft_id", sa.Integer(), sa.ForeignKey("hoa_board_rule_drafts.id"), nullable=False),
        sa.Column("proposal_sha256", sa.String(64), nullable=False),
        sa.Column("quorum_min", sa.Integer(), nullable=False),
        sa.Column("approval_min", sa.Integer(), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("adopted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("adopted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("rule_draft_id", "proposal_sha256", name="uq_hoa_board_rule_adoption_revision"),
    )
    op.create_index(
        "ix_hoa_board_rule_adoption_scope", "hoa_board_rule_adoptions",
        ["organization_id", "association_id", "property_id"],
    )


def downgrade():
    op.drop_index("ix_hoa_board_rule_adoption_scope", table_name="hoa_board_rule_adoptions")
    op.drop_table("hoa_board_rule_adoptions")
