"""HOA reserve GL mapping readiness, no financial transactions.

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c3e5a7b9d1f2"
down_revision = "b2d4f6a8c0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_reserve_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_accounts.id", ondelete="RESTRICT")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", name="uq_hoa_reserve_assoc_property"),
        sa.UniqueConstraint("organization_id", "gl_account_id", name="uq_hoa_reserve_dedicated_gl"),
    )
    for column in ("id", "organization_id", "association_id", "property_id", "gl_account_id", "bank_account_id"):
        op.create_index(f"ix_hoa_reserve_accounts_{column}", "hoa_reserve_accounts", [column])
    op.create_index("ix_hoa_reserve_scope", "hoa_reserve_accounts",
                    ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_reserve_scope", table_name="hoa_reserve_accounts")
    for column in ("bank_account_id", "gl_account_id", "property_id",
                   "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_reserve_accounts_{column}", table_name="hoa_reserve_accounts")
    op.drop_table("hoa_reserve_accounts")
