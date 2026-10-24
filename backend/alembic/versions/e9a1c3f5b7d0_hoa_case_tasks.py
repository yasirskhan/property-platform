"""Create HOA case follow-up tasks.

Revision ID: e9a1c3f5b7d0
Revises: d8f0a2c4e6b9
"""
from alembic import op
import sqlalchemy as sa

revision = "e9a1c3f5b7d0"
down_revision = "d8f0a2c4e6b9"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "hoa_case_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("result_note", sa.String(600)),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", "request_key", name="uq_hoa_case_task_request"),
    )
    op.create_index("ix_hoa_case_task_scope", "hoa_case_tasks", ["organization_id", "association_id", "property_id", "case_id"])

def downgrade():
    op.drop_index("ix_hoa_case_task_scope", table_name="hoa_case_tasks")
    op.drop_table("hoa_case_tasks")
