"""add deleted_at to financial soft deletable records

Revision ID: 13f0a5c9d8e7
Revises: 02eaf4b8c7d6
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "13f0a5c9d8e7"
down_revision = "02eaf4b8c7d6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("deposits") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_deposits_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_insurance") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_insurance_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("management_fee_runs") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_management_fee_runs_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("owner_statements") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_owner_statements_deleted_at", ["deleted_at"], unique=False)

def downgrade() -> None:
    with op.batch_alter_table("owner_statements") as batch:
        batch.drop_index("ix_owner_statements_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("management_fee_runs") as batch:
        batch.drop_index("ix_management_fee_runs_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_insurance") as batch:
        batch.drop_index("ix_property_insurance_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("deposits") as batch:
        batch.drop_index("ix_deposits_deleted_at")
        batch.drop_column("deleted_at")
