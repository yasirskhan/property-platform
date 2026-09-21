# ============================================================
# e5d4a58b8e85_add_property_amenities.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Property amenities — a simple named list per property.
# Pure CRUD, no GL impact.
#
# Revision ID: e5d4a58b8e85
# Revises:     7ca4251074bc  (bank accounts head)
# ============================================================

"""add property amenities

Revision ID: e5d4a58b8e85
Revises: 7ca4251074bc
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "e5d4a58b8e85"
down_revision = "7ca4251074bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_amenities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_property_amenities_organization_id",
        "property_amenities",
        ["organization_id"],
    )
    op.create_index(
        "ix_property_amenities_property_id",
        "property_amenities",
        ["property_id"],
    )
    op.create_index(
        "ix_property_amenities_is_active",
        "property_amenities",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_property_amenities_is_active",
        table_name="property_amenities",
    )
    op.drop_index(
        "ix_property_amenities_property_id",
        table_name="property_amenities",
    )
    op.drop_index(
        "ix_property_amenities_organization_id",
        table_name="property_amenities",
    )
    op.drop_table("property_amenities")