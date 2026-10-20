"""Add scoped preventive schedules and unique work-order occurrences.

Revision ID: 6b0a9c2d4e7f
Revises: 5a9e3c7d1b2f
"""
from alembic import op
import sqlalchemy as sa
revision = "6b0a9c2d4e7f"
down_revision = "5a9e3c7d1b2f"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("preventive_maintenance_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_preventive_maintenance_schedules_organization_id", "preventive_maintenance_schedules", ["organization_id"])
    op.create_index("ix_preventive_schedules_org_due", "preventive_maintenance_schedules", ["organization_id", "active", "next_due_date"])
    op.create_table("preventive_maintenance_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("preventive_maintenance_schedules.id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("schedule_id", "due_date", name="uq_preventive_schedule_occurrence"))

def downgrade():
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT EXISTS(SELECT 1 FROM preventive_maintenance_occurrences)")).scalar():
        raise RuntimeError("Cannot delete recorded preventive occurrences")
    if conn.execute(sa.text("SELECT EXISTS(SELECT 1 FROM preventive_maintenance_schedules)")).scalar():
        raise RuntimeError("Cannot delete saved preventive schedules")
    op.drop_table("preventive_maintenance_occurrences")
    op.drop_index("ix_preventive_schedules_org_due", table_name="preventive_maintenance_schedules")
    op.drop_index("ix_preventive_maintenance_schedules_organization_id", table_name="preventive_maintenance_schedules")
    op.drop_table("preventive_maintenance_schedules")
