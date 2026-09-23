"""add organization accounting lock and data region

Revision ID: e0b8c2d6f5a4
Revises: d9a7b1c5e4f3
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "e0b8c2d6f5a4"
down_revision = "d9a7b1c5e4f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("locked_through_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column(
                "data_region",
                sa.String(length=32),
                nullable=False,
                server_default="us-east-1",
            )
        )
        batch.create_index(
            "ix_organizations_locked_through_date",
            ["locked_through_date"],
            unique=False,
        )
        batch.create_index(
            "ix_organizations_data_region",
            ["data_region"],
            unique=False,
        )

    with op.batch_alter_table("properties") as batch:
        batch.add_column(sa.Column("data_region", sa.String(length=32), nullable=True))
        batch.create_index(
            "ix_properties_data_region",
            ["data_region"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("properties") as batch:
        batch.drop_index("ix_properties_data_region")
        batch.drop_column("data_region")

    with op.batch_alter_table("organizations") as batch:
        batch.drop_index("ix_organizations_data_region")
        batch.drop_index("ix_organizations_locked_through_date")
        batch.drop_column("data_region")
        batch.drop_column("locked_through_date")
