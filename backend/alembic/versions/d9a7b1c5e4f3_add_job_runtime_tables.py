"""add durable job runtime tables

Revision ID: d9a7b1c5e4f3
Revises: c8f6a0b4d3e2
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "d9a7b1c5e4f3"
down_revision = "c8f6a0b4d3e2"
branch_labels = None
depends_on = None


job_status = sa.Enum(
    "PENDING",
    "QUEUED",
    "RUNNING",
    "RETRYING",
    "SUCCEEDED",
    "DEAD_LETTER",
    name="job_status",
    native_enum=False,
    length=24,
)


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_name", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="PENDING"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("arq_job_id", sa.String(length=255), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_name",
            "idempotency_key",
            name="uq_job_runs_name_idempotency",
        ),
    )
    op.create_index("ix_job_runs_job_name", "job_runs", ["job_name"], unique=False)
    op.create_index("ix_job_runs_status", "job_runs", ["status"], unique=False)
    op.create_index("ix_job_runs_arq_job_id", "job_runs", ["arq_job_id"], unique=False)
    op.create_index("ix_job_runs_scheduled_for", "job_runs", ["scheduled_for"], unique=False)
    op.create_index(
        "ix_job_runs_status_scheduled",
        "job_runs",
        ["status", "scheduled_for"],
        unique=False,
    )

    op.create_table(
        "job_dead_letters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_run_id", sa.Integer(), nullable=False),
        sa.Column("job_name", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_run_id"], ["job_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_run_id"),
    )
    op.create_index(
        "ix_job_dead_letters_job_run_id",
        "job_dead_letters",
        ["job_run_id"],
        unique=True,
    )
    op.create_index(
        "ix_job_dead_letters_job_name",
        "job_dead_letters",
        ["job_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_dead_letters_job_name", table_name="job_dead_letters")
    op.drop_index("ix_job_dead_letters_job_run_id", table_name="job_dead_letters")
    op.drop_table("job_dead_letters")

    op.drop_index("ix_job_runs_status_scheduled", table_name="job_runs")
    op.drop_index("ix_job_runs_scheduled_for", table_name="job_runs")
    op.drop_index("ix_job_runs_arq_job_id", table_name="job_runs")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_job_name", table_name="job_runs")
    op.drop_table("job_runs")
