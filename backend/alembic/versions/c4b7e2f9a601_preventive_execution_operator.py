"""Recover preventive schedule execution independently of original authorship.

Revision ID: c4b7e2f9a601
Revises: 7c2e6f0a9b31
"""
from alembic import op
import sqlalchemy as sa

revision = "c4b7e2f9a601"
down_revision = "7c2e6f0a9b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("preventive_maintenance_schedules") as batch:
        batch.add_column(sa.Column(
            "executor_user_id", sa.Integer(),
            sa.ForeignKey("users.id"), nullable=True,
        ))
        batch.create_index(
            "ix_preventive_maintenance_schedules_executor_user_id",
            ["executor_user_id"],
        )


def downgrade() -> None:
    # An assigned executor is business evidence, never silently erase it.
    populated = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM preventive_maintenance_schedules "
        "WHERE executor_user_id IS NOT NULL)"
    )).scalar()
    if populated:
        raise RuntimeError("Cannot drop assigned preventive schedule executors")
    with op.batch_alter_table("preventive_maintenance_schedules") as batch:
        batch.drop_index("ix_preventive_maintenance_schedules_executor_user_id")
        batch.drop_column("executor_user_id")
