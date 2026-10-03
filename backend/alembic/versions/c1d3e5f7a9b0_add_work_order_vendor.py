"""Explicit optional external Vendor company on work orders.

Revision ID: c1d3e5f7a9b0
Revises: b0c2d4e6f8a1
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d3e5f7a9b0"
down_revision = "b0c2d4e6f8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("vendor_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_work_orders_vendor_company", "vendors", ["vendor_id"], ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_work_orders_vendor_id", ["vendor_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.drop_index("ix_work_orders_vendor_id")
        batch.drop_constraint("fk_work_orders_vendor_company", type_="foreignkey")
        batch.drop_column("vendor_id")
