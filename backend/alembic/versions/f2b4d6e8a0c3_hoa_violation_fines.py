"""Recorded HOA board fine decisions and central GL booking.

Revision ID: f2b4d6e8a0c3
Revises: e1a3c5f7b9d2
"""
from alembic import op
import sqlalchemy as sa

revision = "f2b4d6e8a0c3"
down_revision = "e1a3c5f7b9d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_violation_fines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False, unique=True),
        sa.Column("service_record_id", sa.Integer(), sa.ForeignKey("hoa_violation_service_records.id"), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("board_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id")),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("decision_note", sa.Text(), nullable=False),
        sa.Column("hearing_disposition", sa.String(32), nullable=False),
        sa.Column("hearing_held_on", sa.Date()),
        sa.Column("hearing_record_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id")),
        sa.Column("decided_on", sa.Date(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("receivable_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id")),
        sa.Column("income_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id")),
        sa.Column("gl_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id"), unique=True),
        sa.Column("reversal_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id"), unique=True),
        sa.Column("posted_on", sa.Date()),
        sa.Column("reversed_on", sa.Date()),
        sa.Column("reversal_reason", sa.Text()),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_hoa_violation_fine_request"),
    )
    op.create_index("ix_hoa_violation_fine_scope", "hoa_violation_fines",
                    ["organization_id", "association_id", "property_id", "case_id"])


def downgrade():
    op.drop_index("ix_hoa_violation_fine_scope", table_name="hoa_violation_fines")
    op.drop_table("hoa_violation_fines")
