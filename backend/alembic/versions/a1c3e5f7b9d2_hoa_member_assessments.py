"""Recorded HOA assessment decisions and member receivable GL links.

Revision ID: a1c3e5f7b9d2
Revises: f0b2d4e6a8c1
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c3e5f7b9d2"
down_revision = "f0b2d4e6a8c1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_assessment_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("hoa_assessment_proposals.id"), nullable=False, unique=True),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("board_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=False),
        sa.Column("decided_on", sa.Date(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.Column("record_method", sa.String(16), nullable=False),
        sa.Column("supporting_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id")),
        sa.Column("decision_maker_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id")),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id")),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("approved_amount", sa.Numeric(14, 2)),
        sa.Column("proposal_revision_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_assessment_decision_scope", "hoa_assessment_decisions", ["organization_id", "association_id", "property_id"])
    op.create_table(
        "hoa_member_assessment_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("hoa_assessment_decisions.id"), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), sa.ForeignKey("hoa_planned_occurrences.id"), nullable=False, unique=True),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id"), nullable=False),
        sa.Column("receivable_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("income_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("gl_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id"), nullable=False, unique=True),
        sa.Column("reversal_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id"), unique=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("reversal_reason", sa.Text()),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_member_assessment_scope", "hoa_member_assessment_charges", ["organization_id", "association_id", "property_id", "member_user_id"])


def downgrade():
    op.drop_index("ix_hoa_member_assessment_scope", table_name="hoa_member_assessment_charges")
    op.drop_table("hoa_member_assessment_charges")
    op.drop_index("ix_hoa_assessment_decision_scope", table_name="hoa_assessment_decisions")
    op.drop_table("hoa_assessment_decisions")
