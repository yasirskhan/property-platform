"""add deleted_at to platform and property soft deletables

Revision ID: 24a1b6d0e9f8
Revises: 13f0a5c9d8e7
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "24a1b6d0e9f8"
down_revision = "13f0a5c9d8e7"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("platform_users") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_platform_users_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_assignments") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_assignments_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_owners") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_owners_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_amenities") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_amenities_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_appliances") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_appliances_deleted_at", ["deleted_at"], unique=False)

def downgrade() -> None:
    with op.batch_alter_table("property_appliances") as batch:
        batch.drop_index("ix_property_appliances_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_amenities") as batch:
        batch.drop_index("ix_property_amenities_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_owners") as batch:
        batch.drop_index("ix_property_owners_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_assignments") as batch:
        batch.drop_index("ix_property_assignments_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("platform_users") as batch:
        batch.drop_index("ix_platform_users_deleted_at")
        batch.drop_column("deleted_at")
