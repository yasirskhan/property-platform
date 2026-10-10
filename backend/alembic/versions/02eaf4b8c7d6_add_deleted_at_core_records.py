"""add deleted_at to soft deletable core records

Revision ID: 02eaf4b8c7d6
Revises: f1c9d3e7a6b5
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "02eaf4b8c7d6"
down_revision = "f1c9d3e7a6b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bank_accounts") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_bank_accounts_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("bills") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_bills_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("charges") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_charges_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("currencies") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_currencies_deleted_at", ["deleted_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("currencies") as batch:
        batch.drop_index("ix_currencies_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("charges") as batch:
        batch.drop_index("ix_charges_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("bills") as batch:
        batch.drop_index("ix_bills_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("bank_accounts") as batch:
        batch.drop_index("ix_bank_accounts_deleted_at")
        batch.drop_column("deleted_at")
