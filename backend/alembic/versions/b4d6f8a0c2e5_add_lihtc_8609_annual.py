"""Bounded per-building annual Form 8609-A reference index.

Revision ID: b4d6f8a0c2e5
Revises: a3c5e7f9b1d4
"""
from alembic import op
import sqlalchemy as sa

revision = "b4d6f8a0c2e5"
down_revision = "a3c5e7f9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_lihtc_8609_annual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("allocation_category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["affordable_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["building_id"], ["affordable_lihtc_buildings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "building_id", "tax_year",
                            "allocation_category", name="uq_lihtc_8609_annual_reference"),
    )
    for name in ("id", "organization_id", "property_id", "program_id", "building_id"):
        op.create_index(f"ix_affordable_lihtc_8609_annual_{name}",
                        "affordable_lihtc_8609_annual", [name])
    op.create_index("ix_lihtc_8609_annual_scope",
                    "affordable_lihtc_8609_annual",
                    ["organization_id", "property_id", "program_id", "building_id", "tax_year"])


def downgrade() -> None:
    op.drop_index("ix_lihtc_8609_annual_scope", table_name="affordable_lihtc_8609_annual")
    for name in ("building_id", "program_id", "property_id", "organization_id", "id"):
        op.drop_index(f"ix_affordable_lihtc_8609_annual_{name}",
                      table_name="affordable_lihtc_8609_annual")
    op.drop_table("affordable_lihtc_8609_annual")
