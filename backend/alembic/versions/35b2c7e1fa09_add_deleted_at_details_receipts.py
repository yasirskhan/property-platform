"""add deleted_at to property detail and receipt records

Revision ID: 35b2c7e1fa09
Revises: 24a1b6d0e9f8
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "35b2c7e1fa09"
down_revision = "24a1b6d0e9f8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("property_improvements") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_improvements_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("property_photos") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_property_photos_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("receipts") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_receipts_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("screening_providers") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_screening_providers_deleted_at", ["deleted_at"], unique=False)

def downgrade() -> None:
    with op.batch_alter_table("screening_providers") as batch:
        batch.drop_index("ix_screening_providers_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("receipts") as batch:
        batch.drop_index("ix_receipts_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_photos") as batch:
        batch.drop_index("ix_property_photos_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("property_improvements") as batch:
        batch.drop_index("ix_property_improvements_deleted_at")
        batch.drop_column("deleted_at")
