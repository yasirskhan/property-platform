# ============================================================
# dadbb391cc03_add_property_appliances.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Property appliances — one row per physical appliance on a
# property (Fridge, Washer, Dryer, Dishwasher, etc.).
# Pure CRUD, no GL impact.
#
# Revision ID: dadbb391cc03
# Revises:     e5d4a58b8e85  (property amenities head)
# ============================================================

"""add property appliances

Revision ID: dadbb391cc03
Revises: e5d4a58b8e85
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "dadbb391cc03"
down_revision = "e5d4a58b8e85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_appliances",
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
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("model_number", sa.String(length=120), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column(
            "purchase_price",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
        sa.Column("warranty_expires", sa.Date(), nullable=True),
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
        "ix_property_appliances_organization_id",
        "property_appliances",
        ["organization_id"],
    )
    op.create_index(
        "ix_property_appliances_property_id",
        "property_appliances",
        ["property_id"],
    )
    op.create_index(
        "ix_property_appliances_is_active",
        "property_appliances",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_property_appliances_is_active",
        table_name="property_appliances",
    )
    op.drop_index(
        "ix_property_appliances_property_id",
        table_name="property_appliances",
    )
    op.drop_index(
        "ix_property_appliances_organization_id",
        table_name="property_appliances",
    )
    op.drop_table("property_appliances")