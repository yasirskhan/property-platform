"""Optional end date for bounded preventive schedules.

Revision ID: 7c2e6f0a9b31
Revises: 6b0a9c2d4e7f
"""
from alembic import op
import sqlalchemy as sa

revision = "7c2e6f0a9b31"
down_revision = "6b0a9c2d4e7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("preventive_maintenance_schedules") as batch:
        batch.add_column(sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    # Never discard explicitly configured schedule end dates.
    evidence = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM preventive_maintenance_schedules WHERE end_date IS NOT NULL)"
    )).scalar()
    if evidence:
        raise RuntimeError("Cannot drop populated preventive schedule end dates")
    with op.batch_alter_table("preventive_maintenance_schedules") as batch:
        batch.drop_column("end_date")
