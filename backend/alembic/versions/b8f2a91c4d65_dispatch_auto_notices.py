"""System-authored durable dispatch attention, no external delivery."""
from alembic import op
import sqlalchemy as sa

revision = "b8f2a91c4d65"
down_revision = "f6c8e2a104d9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_dispatch_auto_notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("crew_user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("timeout_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crew_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["group_id"], ["maintenance_dispatch_groups.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("work_order_id", "assigned_at", name="uq_dispatch_auto_notice_assignment"),
        sa.CheckConstraint("timeout_minutes BETWEEN 1 AND 1440", name="ck_dispatch_auto_notice_timeout"),
    )
    for key in ("organization_id", "work_order_id"):
        op.create_index("ix_maintenance_dispatch_auto_notices_" + key,
                        "maintenance_dispatch_auto_notices", [key])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM maintenance_dispatch_auto_notices LIMIT 1")).first():
        raise RuntimeError("Cannot remove durable automated dispatch attention evidence")
    for key in ("organization_id", "work_order_id"):
        op.drop_index("ix_maintenance_dispatch_auto_notices_" + key,
                      table_name="maintenance_dispatch_auto_notices")
    op.drop_table("maintenance_dispatch_auto_notices")
