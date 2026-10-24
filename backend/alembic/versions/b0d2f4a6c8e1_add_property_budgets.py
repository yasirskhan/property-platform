"""Persist monthly property budget targets without changing ledger postings.

Revision ID: b0d2f4a6c8e1
Revises: a9c1e3f5b7d0
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "b0d2f4a6c8e1"
down_revision = "a9c1e3f5b7d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_budget_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("gl_account_id", sa.Integer(), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gl_account_id"], ["gl_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "property_id", "gl_account_id",
            "calendar_year", "month", name="uq_property_budget_period_account",
        ),
    )
    for column in ("id", "organization_id", "property_id", "gl_account_id", "calendar_year"):
        op.create_index(f"ix_property_budget_lines_{column}", "property_budget_lines", [column], unique=False)


def downgrade() -> None:
    for column in ("calendar_year", "gl_account_id", "property_id", "organization_id", "id"):
        op.drop_index(f"ix_property_budget_lines_{column}", table_name="property_budget_lines")
    op.drop_table("property_budget_lines")
