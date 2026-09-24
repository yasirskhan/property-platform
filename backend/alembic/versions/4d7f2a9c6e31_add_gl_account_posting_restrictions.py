"""add GL account posting restrictions

Revision ID: 4d7f2a9c6e31
Revises: 8c4e2a7d1f90
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "4d7f2a9c6e31"
down_revision = "8c4e2a7d1f90"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "gl_account_posting_restrictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("gl_account_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gl_account_id"], ["gl_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "gl_account_id", "role", name="uq_gl_account_posting_restriction"),
    )
    op.create_index("ix_gl_account_posting_restrictions_organization_id", "gl_account_posting_restrictions", ["organization_id"], unique=False)
    op.create_index("ix_gl_account_posting_restrictions_gl_account_id", "gl_account_posting_restrictions", ["gl_account_id"], unique=False)
    op.create_index("ix_gl_account_posting_restrictions_role", "gl_account_posting_restrictions", ["role"], unique=False)
    op.create_index("ix_gl_account_posting_restrictions_org_role", "gl_account_posting_restrictions", ["organization_id", "role"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_gl_account_posting_restrictions_org_role", table_name="gl_account_posting_restrictions")
    op.drop_index("ix_gl_account_posting_restrictions_role", table_name="gl_account_posting_restrictions")
    op.drop_index("ix_gl_account_posting_restrictions_gl_account_id", table_name="gl_account_posting_restrictions")
    op.drop_index("ix_gl_account_posting_restrictions_organization_id", table_name="gl_account_posting_restrictions")
    op.drop_table("gl_account_posting_restrictions")
