"""finish deleted_at coverage for remaining soft deletables

Revision ID: 46c3d8f2ab10
Revises: 35b2c7e1fa09
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "46c3d8f2ab10"
down_revision = "35b2c7e1fa09"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("property_taxes") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_taxes_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_organizations_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_users_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_utilities") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_utilities_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("trash_pickup_schedule") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_trash_pickup_schedule_deleted_at", ["deleted_at"], unique=False)

def downgrade() -> None:
    with op.batch_alter_table("trash_pickup_schedule") as batch:
        batch.drop_index("ix_trash_pickup_schedule_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_utilities") as batch:
        batch.drop_index("ix_property_utilities_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("organizations") as batch:
        batch.drop_index("ix_organizations_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_taxes") as batch:
        batch.drop_index("ix_property_taxes_deleted_at")
        batch.drop_column("deleted_at")
