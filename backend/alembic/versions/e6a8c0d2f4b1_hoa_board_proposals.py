"""Staff HOA board roster and proposed thresholds, never effective voting.

Revision ID: e6a8c0d2f4b1
Revises: d5f7a9b1c3e4
"""
from alembic import op
import sqlalchemy as sa

revision = "e6a8c0d2f4b1"
down_revision = "d5f7a9b1c3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_board_seats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposed_role", sa.String(20), nullable=False),
        sa.Column("staff_voting_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", "contact_link_id", name="uq_hoa_board_seat_link"),
    )
    for field in ("organization_id", "association_id", "property_id", "contact_link_id"):
        op.create_index(f"ix_hoa_board_seats_{field}", "hoa_board_seats", [field])
    op.create_index("ix_hoa_board_seat_scope", "hoa_board_seats",
                    ["organization_id", "association_id", "property_id", "is_active"])
    op.create_table(
        "hoa_board_rule_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_quorum_min", sa.Integer(), nullable=True),
        sa.Column("proposed_approval_min", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", name="uq_hoa_board_rule_property"),
    )
    for field in ("organization_id", "association_id", "property_id"):
        op.create_index(f"ix_hoa_board_rule_drafts_{field}", "hoa_board_rule_drafts", [field])


def downgrade() -> None:
    for field in ("property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_board_rule_drafts_{field}", table_name="hoa_board_rule_drafts")
    op.drop_table("hoa_board_rule_drafts")
    op.drop_index("ix_hoa_board_seat_scope", table_name="hoa_board_seats")
    for field in ("contact_link_id", "property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_board_seats_{field}", table_name="hoa_board_seats")
    op.drop_table("hoa_board_seats")
