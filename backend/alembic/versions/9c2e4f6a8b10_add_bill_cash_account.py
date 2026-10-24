"""add bill default cash account

Revision ID: 9c2e4f6a8b10
Revises: 6a1d9e3f4b72
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "9c2e4f6a8b10"
down_revision = "6a1d9e3f4b72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bills") as batch_op:
        batch_op.add_column(
            sa.Column("cash_gl_account_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_bills_cash_gl_account_id_gl_accounts",
            "gl_accounts",
            ["cash_gl_account_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_bills_cash_gl_account_id",
            ["cash_gl_account_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("bills") as batch_op:
        batch_op.drop_index("ix_bills_cash_gl_account_id")
        batch_op.drop_constraint(
            "fk_bills_cash_gl_account_id_gl_accounts",
            type_="foreignkey",
        )
        batch_op.drop_column("cash_gl_account_id")
