"""Staff ballot observation records, never official HOA voting.

Revision ID: f7b9d1e3a5c2
Revises: e6a8c0d2f4b1
"""
from alembic import op
import sqlalchemy as sa

revision = "f7b9d1e3a5c2"
down_revision = "e6a8c0d2f4b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_ballot_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_draft_id", sa.Integer(), sa.ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("motion_draft_id", sa.Integer(), sa.ForeignKey("hoa_motion_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("staff_reported_choice", sa.String(12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("motion_draft_id", "board_seat_id", name="uq_hoa_ballot_motion_seat"),
    )
    for field in ("organization_id", "association_id", "property_id",
                  "meeting_draft_id", "motion_draft_id", "board_seat_id"):
        op.create_index(f"ix_hoa_ballot_records_{field}", "hoa_ballot_records", [field])
    op.create_index("ix_hoa_ballot_scope", "hoa_ballot_records",
                    ["organization_id", "association_id", "property_id", "meeting_draft_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_ballot_scope", table_name="hoa_ballot_records")
    for field in ("board_seat_id", "motion_draft_id", "meeting_draft_id",
                  "property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_ballot_records_{field}", table_name="hoa_ballot_records")
    op.drop_table("hoa_ballot_records")
