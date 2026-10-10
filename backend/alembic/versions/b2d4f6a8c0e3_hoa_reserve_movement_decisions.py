"""Board-authorized reserve GL book movements.

Revision ID: b2d4f6a8c0e3
Revises: a1c3e5f7b9d2
"""
from alembic import op
import sqlalchemy as sa

revision = "b2d4f6a8c0e3"
down_revision = "a1c3e5f7b9d2"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "hoa_reserve_movement_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("hoa_reserve_movement_drafts.id"), nullable=False, unique=True),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("maker_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("record_method", sa.String(16), nullable=False),
        sa.Column("supporting_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id")),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=False),
        sa.Column("decided_on", sa.Date(), nullable=False),
        sa.Column("approved_amount", sa.Numeric(14,2)),
        sa.Column("reserve_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("counterparty_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("gl_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id")),
        sa.Column("reversal_transaction_id", sa.Integer(), sa.ForeignKey("gl_transactions.id")),
        sa.Column("posted_on", sa.Date()),
        sa.Column("reversed_on", sa.Date()),
        sa.Column("reversal_reason", sa.String(600)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_reserve_decision_scope", "hoa_reserve_movement_decisions",
                    ["organization_id", "association_id", "property_id"])

def downgrade():
    op.drop_index("ix_hoa_reserve_decision_scope", table_name="hoa_reserve_movement_decisions")
    op.drop_table("hoa_reserve_movement_decisions")
