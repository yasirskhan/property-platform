"""HOA fine-specific receipt allocations with protected central GL reversal.

Revision ID: a3c5e7f9b1d4
Revises: f2b4d6e8a0c3
"""
from alembic import op
import sqlalchemy as sa

revision = "a3c5e7f9b1d4"
down_revision = "f2b4d6e8a0c3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hoa_violation_fines", sa.Column(
        "amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0.00",
    ))
    op.create_table(
        "hoa_violation_fine_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("fine_id", sa.Integer(), sa.ForeignKey("hoa_violation_fines.id"), nullable=False),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("receipts.id"), nullable=False, unique=True),
        sa.Column("cash_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("payment_reference", sa.String(60), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="POSTED"),
        sa.Column("reversal_receipt_id", sa.Integer(), sa.ForeignKey("receipts.id"), unique=True),
        sa.Column("reversed_on", sa.Date()),
        sa.Column("reversal_reason", sa.String(600)),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reversed_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_hoa_fine_payment_request"),
    )
    op.create_index("ix_hoa_fine_payment_scope", "hoa_violation_fine_payments",
                    ["organization_id", "association_id", "property_id", "fine_id"])


def downgrade():
    op.drop_index("ix_hoa_fine_payment_scope", table_name="hoa_violation_fine_payments")
    op.drop_table("hoa_violation_fine_payments")
    op.drop_column("hoa_violation_fines", "amount_paid")
