"""Independent crew time corrections retain original evidence.

Revision ID: b5d0c8e7a214
Revises: f4b82c1a9d60
"""
from alembic import op
import sqlalchemy as sa

revision = "b5d0c8e7a214"
down_revision = "f4b82c1a9d60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_order_time_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("time_entry_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("proposed_started_at", sa.DateTime(), nullable=False),
        sa.Column("proposed_ended_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_reason", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], name="fk_time_correct_order", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["time_entry_id"], ["work_order_time_entries.id"], name="fk_time_correct_entry", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name="fk_time_correct_requester", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], name="fk_time_correct_reviewer", ondelete="RESTRICT"),
        sa.CheckConstraint("duration_minutes BETWEEN 1 AND 1440", name="ck_time_correction_minutes"),
        sa.CheckConstraint("proposed_ended_at > proposed_started_at", name="ck_time_correction_order"),
        sa.CheckConstraint("status IN ('pending','approved','denied')", name="ck_time_correction_status"),
    )
    op.create_index("ix_work_order_time_corrections_work_order_id", "work_order_time_corrections", ["work_order_id"])
    op.create_index("ix_work_order_time_corrections_time_entry_id", "work_order_time_corrections", ["time_entry_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM work_order_time_corrections)")).scalar():
        raise RuntimeError("Cannot discard time correction review evidence")
    op.drop_index("ix_work_order_time_corrections_time_entry_id", table_name="work_order_time_corrections")
    op.drop_index("ix_work_order_time_corrections_work_order_id", table_name="work_order_time_corrections")
    op.drop_table("work_order_time_corrections")
