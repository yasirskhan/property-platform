"""add private saved report configurations

Revision ID: b4e6a8c0d2f5
Revises: a3d5f7b9c1e4
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "b4e6a8c0d2f5"
down_revision = "a3d5f7b9c1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("report_key", sa.String(length=100), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_reports_id", "saved_reports", ["id"], unique=False)
    op.create_index("ix_saved_reports_organization_id", "saved_reports", ["organization_id"], unique=False)
    op.create_index("ix_saved_reports_user_id", "saved_reports", ["user_id"], unique=False)
    op.create_index("ix_saved_reports_scope", "saved_reports", ["organization_id", "user_id", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saved_reports_scope", table_name="saved_reports")
    op.drop_index("ix_saved_reports_user_id", table_name="saved_reports")
    op.drop_index("ix_saved_reports_organization_id", table_name="saved_reports")
    op.drop_index("ix_saved_reports_id", table_name="saved_reports")
    op.drop_table("saved_reports")
