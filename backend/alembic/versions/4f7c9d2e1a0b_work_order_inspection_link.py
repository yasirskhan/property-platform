"""Bind manually created work orders to authorized source inspection evidence.

Revision ID: 4f7c9d2e1a0b
Revises: 3e6a8b0d91f2
"""
from alembic import op
import sqlalchemy as sa

revision = "4f7c9d2e1a0b"
down_revision = "3e6a8b0d91f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("source_inspection_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_work_orders_source_inspection_id", "unit_inspection_records",
            ["source_inspection_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_index("ix_work_orders_source_inspection_id", ["source_inspection_id"], unique=False)


def downgrade() -> None:
    populated = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM work_orders WHERE source_inspection_id IS NOT NULL)"
    )).scalar()
    if populated:
        raise RuntimeError("Cannot drop existing work-order inspection links")
    with op.batch_alter_table("work_orders") as batch:
        batch.drop_index("ix_work_orders_source_inspection_id")
        batch.drop_constraint("fk_work_orders_source_inspection_id", type_="foreignkey")
        batch.drop_column("source_inspection_id")
