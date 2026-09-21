# ============================================================
# 35529ce17750_add_property_improvements.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Property improvements — one row per renovation / upgrade on
# a property (kitchen remodel, roof replacement, etc.).
# Pure CRUD, no GL impact.
#
# Revision ID: 35529ce17750
# Revises:     dadbb391cc03  (property appliances head)
# ============================================================

"""add property improvements

Revision ID: 35529ce17750
Revises: dadbb391cc03
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "35529ce17750"
down_revision = "dadbb391cc03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_improvements",
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
        sa.Column("improvement_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "cost",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
        sa.Column("contractor", sa.String(length=200), nullable=True),
        # Kitchen | Bath | Roof | HVAC | Flooring | Electrical |
        # Plumbing | Exterior | Other
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
        "ix_property_improvements_organization_id",
        "property_improvements",
        ["organization_id"],
    )
    op.create_index(
        "ix_property_improvements_property_id",
        "property_improvements",
        ["property_id"],
    )
    op.create_index(
        "ix_property_improvements_improvement_date",
        "property_improvements",
        ["improvement_date"],
    )
    op.create_index(
        "ix_property_improvements_is_active",
        "property_improvements",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_property_improvements_is_active",
        table_name="property_improvements",
    )
    op.drop_index(
        "ix_property_improvements_improvement_date",
        table_name="property_improvements",
    )
    op.drop_index(
        "ix_property_improvements_property_id",
        table_name="property_improvements",
    )
    op.drop_index(
        "ix_property_improvements_organization_id",
        table_name="property_improvements",
    )
    op.drop_table("property_improvements")