"""Add organization-scoped mail-merge letter templates.

Revision ID: a9c1e3f5b7d0
Revises: f8c0d2e4a6b9
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "a9c1e3f5b7d0"
down_revision = "f8c0d2e4a6b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "letter_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_letter_templates_id", "letter_templates", ["id"], unique=False)
    op.create_index("ix_letter_templates_organization_id", "letter_templates", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_letter_templates_organization_id", table_name="letter_templates")
    op.drop_index("ix_letter_templates_id", table_name="letter_templates")
    op.drop_table("letter_templates")
