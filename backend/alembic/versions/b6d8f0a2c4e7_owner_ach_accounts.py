"""add owner ACH account setup

Revision ID: b6d8f0a2c4e7
Revises: a4b6c8d0e2f1
"""
from alembic import op
import sqlalchemy as sa

revision = "b6d8f0a2c4e7"
down_revision = "a4b6c8d0e2f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "owner_ach_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("account_holder_name", sa.String(length=120), nullable=False),
        sa.Column("bank_name", sa.String(length=200), nullable=True),
        sa.Column("routing_number", sa.String(length=9), nullable=False),
        sa.Column("account_number", sa.String(length=40), nullable=False),
        sa.Column("account_type", sa.String(length=10), nullable=False, server_default="CHECKING"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organization_id", "owner_id", name="uq_owner_ach_org_owner"),
    )
    op.create_index(
        "ix_owner_ach_accounts_organization_id",
        "owner_ach_accounts",
        ["organization_id"],
    )
    op.create_index(
        "ix_owner_ach_accounts_owner_id",
        "owner_ach_accounts",
        ["owner_id"],
    )
    op.create_index(
        "ix_owner_ach_accounts_is_enabled",
        "owner_ach_accounts",
        ["is_enabled"],
    )


def downgrade():
    op.drop_index("ix_owner_ach_accounts_is_enabled", table_name="owner_ach_accounts")
    op.drop_index("ix_owner_ach_accounts_owner_id", table_name="owner_ach_accounts")
    op.drop_index("ix_owner_ach_accounts_organization_id", table_name="owner_ach_accounts")
    op.drop_table("owner_ach_accounts")
