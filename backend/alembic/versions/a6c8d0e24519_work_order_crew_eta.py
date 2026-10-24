"""Crew arrival estimate for accepted work-order dispatches.

Revision ID: a6c8d0e24519
Revises: e1b9c7d2a540
"""
from alembic import op
import sqlalchemy as sa

revision = "a6c8d0e24519"
down_revision = "e1b9c7d2a540"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("crew_eta_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    used = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM work_orders WHERE crew_eta_at IS NOT NULL)"
    )).scalar()
    if used:
        raise RuntimeError("Cannot discard recorded crew arrival estimates")
    with op.batch_alter_table("work_orders") as batch:
        batch.drop_column("crew_eta_at")
