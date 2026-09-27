"""Explicit nullable Vendor company link on posted Bills; no historical auto-match.

Revision ID: b0c2d4e6f8a1
Revises: a9b1c3d5e7f0
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "b0c2d4e6f8a1"
down_revision = "a9b1c3d5e7f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bills") as batch:
        batch.add_column(sa.Column("vendor_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_bills_vendor_company", "vendors", ["vendor_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index("ix_bills_vendor_id", ["vendor_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("bills") as batch:
        batch.drop_index("ix_bills_vendor_id")
        batch.drop_constraint("fk_bills_vendor_company", type_="foreignkey")
        batch.drop_column("vendor_id")
