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
    with op.batch_alter_table("application_payments") as batch:
        batch.add_column(sa.Column("receipt_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_application_payments_receipt_id", "receipts",
            ["receipt_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_index("ix_application_payments_receipt_id", ["receipt_id"], unique=True)


def downgrade():
    with op.batch_alter_table("application_payments") as batch:
        batch.drop_index("ix_application_payments_receipt_id")
        batch.drop_constraint("fk_application_payments_receipt_id", type_="foreignkey")
        batch.drop_column("receipt_id")
