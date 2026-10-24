"""Property crew on-call schedule with auditable cancellation.

Revision ID: a0c7d4e19f32
Revises: d3f7c0a198be
"""
from alembic import op
import sqlalchemy as sa

revision = "a0c7d4e19f32"
down_revision = "d3f7c0a198be"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_on_call_shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("crew_user_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("cancellation_reason", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_on_call_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_on_call_property", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crew_user_id"], ["users.id"], name="fk_on_call_crew", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_on_call_creator", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"], name="fk_on_call_canceller", ondelete="SET NULL"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_on_call_shift_order"),
    )
    op.create_index("ix_maintenance_on_call_shifts_organization_id", "maintenance_on_call_shifts", ["organization_id"])
    op.create_index("ix_maintenance_on_call_shifts_property_id", "maintenance_on_call_shifts", ["property_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM maintenance_on_call_shifts)")).scalar():
        raise RuntimeError("Cannot discard scheduled on-call and cancellation evidence")
    op.drop_index("ix_maintenance_on_call_shifts_property_id", table_name="maintenance_on_call_shifts")
    op.drop_index("ix_maintenance_on_call_shifts_organization_id", table_name="maintenance_on_call_shifts")
    op.drop_table("maintenance_on_call_shifts")
