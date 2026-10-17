"""add platform actor to immutable audit log

Revision ID: c8f6a0b4d3e2
Revises: b7d5e9a3c2f1
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "c8f6a0b4d3e2"
down_revision = "b7d5e9a3c2f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.add_column(sa.Column("platform_user_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            "ix_audit_log_platform_user_id",
            ["platform_user_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_audit_log_platform_user_id",
            "platform_users",
            ["platform_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_constraint(
            "fk_audit_log_platform_user_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_audit_log_platform_user_id")
        batch_op.drop_column("platform_user_id")
