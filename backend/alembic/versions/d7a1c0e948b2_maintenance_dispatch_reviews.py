"""Durable manual dispatch review with one-open-case invariant.

Revision ID: d7a1c0e948b2
Revises: c9e52d4f1b78
"""
from alembic import op
import sqlalchemy as sa

revision = "d7a1c0e948b2"
down_revision = "c9e52d4f1b78"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_dispatch_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("open_work_order_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("opened_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["open_work_order_id"], ["work_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["opened_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("open_work_order_id", name="uq_maintenance_dispatch_review_open"),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_maintenance_dispatch_review_status"),
        sa.CheckConstraint(
            "(status = 'open' AND open_work_order_id IS NOT NULL AND closed_at IS NULL)"
            " OR (status = 'closed' AND open_work_order_id IS NULL AND closed_at IS NOT NULL)",
            name="ck_maintenance_dispatch_review_lifecycle",
        ),
    )
    for col in ("organization_id", "work_order_id"):
        op.create_index("ix_maintenance_dispatch_reviews_" + col, "maintenance_dispatch_reviews", [col])


def downgrade():
    # Never erase a customer's review or historic dispatch evidence.
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM maintenance_dispatch_reviews)")).scalar():
        raise RuntimeError("Cannot discard recorded dispatch review evidence")
    for col in ("organization_id", "work_order_id"):
        op.drop_index("ix_maintenance_dispatch_reviews_" + col, table_name="maintenance_dispatch_reviews")
    op.drop_table("maintenance_dispatch_reviews")
