"""Link one posted fee receipt to an application payment.

Revision ID: f3e5a7c9d1b2
Revises: f2e4a6c8d0b1
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "f3e5a7c9d1b2"
down_revision = "f2e4a6c8d0b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("application_payments", sa.Column("receipt_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_application_payments_receipt_id", "application_payments", "receipts",
        ["receipt_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_application_payments_receipt_id", "application_payments", ["receipt_id"], unique=True)


def downgrade():
    op.drop_index("ix_application_payments_receipt_id", table_name="application_payments")
    op.drop_constraint("fk_application_payments_receipt_id", "application_payments", type_="foreignkey")
    op.drop_column("application_payments", "receipt_id")
