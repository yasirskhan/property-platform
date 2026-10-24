"""Crew work-time evidence separate from payroll, bills and tenant charges.

Revision ID: f4b82c1a9d60
Revises: a6c8d0e24519
"""
from alembic import op
import sqlalchemy as sa

revision = "f4b82c1a9d60"
down_revision = "a6c8d0e24519"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_order_time_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("crew_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"],
                                name="fk_crew_time_work_order", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crew_user_id"], ["users.id"],
                                name="fk_crew_time_user", ondelete="RESTRICT"),
        sa.CheckConstraint("duration_minutes BETWEEN 1 AND 1440",
                           name="ck_crew_time_minutes"),
        sa.CheckConstraint("ended_at > started_at", name="ck_crew_time_order"),
    )
    op.create_index("ix_work_order_time_entries_work_order_id", "work_order_time_entries", ["work_order_id"])
    op.create_index("ix_work_order_time_entries_crew_user_id", "work_order_time_entries", ["crew_user_id"])
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""CREATE OR REPLACE FUNCTION prevent_crew_time_mutation()
            RETURNS trigger AS $
            BEGIN RAISE EXCEPTION 'work_order_time_entries is append-only'; END;
            $ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER crew_time_immutable
            BEFORE UPDATE OR DELETE ON work_order_time_entries
            FOR EACH ROW EXECUTE FUNCTION prevent_crew_time_mutation()""")
    elif dialect == "sqlite":
        op.execute("""CREATE TRIGGER crew_time_no_update BEFORE UPDATE ON work_order_time_entries
            BEGIN SELECT RAISE(ABORT, 'work_order_time_entries is append-only'); END""")
        op.execute("""CREATE TRIGGER crew_time_no_delete BEFORE DELETE ON work_order_time_entries
            BEGIN SELECT RAISE(ABORT, 'work_order_time_entries is append-only'); END""")


def downgrade() -> None:
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM work_order_time_entries)"
    )).scalar():
        raise RuntimeError("Cannot discard existing crew time evidence")
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS crew_time_immutable ON work_order_time_entries")
        op.execute("DROP FUNCTION IF EXISTS prevent_crew_time_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS crew_time_no_update")
        op.execute("DROP TRIGGER IF EXISTS crew_time_no_delete")
    op.drop_index("ix_work_order_time_entries_crew_user_id", table_name="work_order_time_entries")
    op.drop_index("ix_work_order_time_entries_work_order_id", table_name="work_order_time_entries")
    op.drop_table("work_order_time_entries")
