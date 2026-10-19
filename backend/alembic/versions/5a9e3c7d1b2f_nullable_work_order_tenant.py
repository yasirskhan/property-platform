"""Allow tenantless staff-originated work orders, preserving historical rows.

Revision ID: 5a9e3c7d1b2f
Revises: 4f7c9d2e1a0b
"""
from alembic import op
import sqlalchemy as sa

revision = "5a9e3c7d1b2f"
down_revision = "4f7c9d2e1a0b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.alter_column(
            "tenant_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )


def downgrade() -> None:
    # Existing tenantless staff records must not be assigned a fake tenant.
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM work_orders WHERE tenant_id IS NULL)"
    )).scalar():
        raise RuntimeError("Cannot make tenant_id required while tenantless work orders exist")
    with op.batch_alter_table("work_orders") as batch:
        batch.alter_column(
            "tenant_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )
