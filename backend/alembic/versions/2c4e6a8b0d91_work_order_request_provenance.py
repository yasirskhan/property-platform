"""Additive work-order requester provenance, leaving legacy tenant_id unchanged.

Revision ID: 2c4e6a8b0d91
Revises: 1b8d3f6a9c20
"""
from alembic import op
import sqlalchemy as sa

revision = "2c4e6a8b0d91"
down_revision = "1b8d3f6a9c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("request_origin", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("requested_by_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_work_orders_requested_by_user_id",
            "users", ["requested_by_user_id"], ["id"],
        )
        batch.create_index("ix_work_orders_requested_by_user_id", ["requested_by_user_id"], unique=False)


def downgrade() -> None:
    # Provenance contains historical evidence. Do not silently delete it.
    raise RuntimeError("Work-order request provenance migration is intentionally irreversible")
