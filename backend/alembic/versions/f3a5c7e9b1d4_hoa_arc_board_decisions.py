"""Store final ARC board decisions and association member fee postings.

Revision ID: f3a5c7e9b1d4
Revises: e2f4a6c8b0d3
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a5c7e9b1d4"
down_revision = "e2f4a6c8b0d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_arc_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("hoa_arc_applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("board_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="SET NULL")),
        sa.Column("notification_status", sa.String(32), nullable=False, server_default="NO_VERIFIED_RECIPIENT"),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
    )
    for name in ("organization_id", "association_id", "property_id"):
        op.create_index(f"ix_hoa_arc_decisions_{name}", "hoa_arc_decisions", [name])
    op.create_index("ix_hoa_arc_decision_scope", "hoa_arc_decisions", ["organization_id", "association_id", "property_id"])
    op.create_table(
        "hoa_arc_member_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("hoa_arc_applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gl_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("income_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receivable_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name in ("organization_id", "association_id", "property_id", "member_user_id"):
        op.create_index(f"ix_hoa_arc_member_charges_{name}", "hoa_arc_member_charges", [name])
    op.create_index(
        "ix_hoa_arc_member_charge_scope", "hoa_arc_member_charges",
        ["organization_id", "association_id", "property_id", "member_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hoa_arc_member_charge_scope", table_name="hoa_arc_member_charges")
    for name in ("member_user_id", "property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_arc_member_charges_{name}", table_name="hoa_arc_member_charges")
    op.drop_table("hoa_arc_member_charges")
    op.drop_index("ix_hoa_arc_decision_scope", table_name="hoa_arc_decisions")
    for name in ("property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_arc_decisions_{name}", table_name="hoa_arc_decisions")
    op.drop_table("hoa_arc_decisions")
