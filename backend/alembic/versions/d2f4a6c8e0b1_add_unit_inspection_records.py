"""Minimal append-only staff-entered inspection records for Phase 3.7 report.

Revision ID: d2f4a6c8e0b1
Revises: c1e3f5a7b9d2
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "d2f4a6c8e0b1"
down_revision = "c1e3f5a7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "unit_inspection_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("inspection_date", sa.Date(), nullable=False),
        sa.Column("recorded_condition", sa.String(length=24), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_unit_inspection_records_id", "unit_inspection_records", ["id"], unique=False)
    op.create_index("ix_unit_inspection_records_organization_id", "unit_inspection_records", ["organization_id"], unique=False)
    op.create_index("ix_unit_inspection_records_property_id", "unit_inspection_records", ["property_id"], unique=False)
    op.create_index("ix_unit_inspection_records_unit_id", "unit_inspection_records", ["unit_id"], unique=False)
    op.create_index("ix_unit_inspection_records_inspection_date", "unit_inspection_records", ["inspection_date"], unique=False)
    op.create_index("ix_unit_inspections_org_property_date", "unit_inspection_records", ["organization_id", "property_id", "inspection_date"], unique=False)


def downgrade() -> None:
    for index in (
        "ix_unit_inspections_org_property_date",
        "ix_unit_inspection_records_inspection_date",
        "ix_unit_inspection_records_unit_id",
        "ix_unit_inspection_records_property_id",
        "ix_unit_inspection_records_organization_id",
        "ix_unit_inspection_records_id",
    ):
        op.drop_index(index, table_name="unit_inspection_records")
    op.drop_table("unit_inspection_records")
