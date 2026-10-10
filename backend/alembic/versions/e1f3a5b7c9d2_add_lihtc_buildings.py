"""Staff-recorded LIHTC agency building IDs, not verified IRS certificates.

Revision ID: e1f3a5b7c9d2
Revises: d0e2f4a6b8c1
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f3a5b7c9d2"
down_revision = "d0e2f4a6b8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_lihtc_buildings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("building_label", sa.String(length=100), nullable=False),
        sa.Column("agency_bin", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("recorded_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["affordable_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "program_id", "agency_bin",
                            name="uq_lihtc_building_bin"),
    )
    op.create_index("ix_affordable_lihtc_buildings_id", "affordable_lihtc_buildings", ["id"])
    op.create_index("ix_affordable_lihtc_buildings_organization_id", "affordable_lihtc_buildings", ["organization_id"])
    op.create_index("ix_affordable_lihtc_buildings_property_id", "affordable_lihtc_buildings", ["property_id"])
    op.create_index("ix_affordable_lihtc_buildings_program_id", "affordable_lihtc_buildings", ["program_id"])
    op.create_index("ix_lihtc_building_scope", "affordable_lihtc_buildings",
                    ["organization_id", "property_id", "program_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_lihtc_building_scope", table_name="affordable_lihtc_buildings")
    op.drop_index("ix_affordable_lihtc_buildings_program_id", table_name="affordable_lihtc_buildings")
    op.drop_index("ix_affordable_lihtc_buildings_property_id", table_name="affordable_lihtc_buildings")
    op.drop_index("ix_affordable_lihtc_buildings_organization_id", table_name="affordable_lihtc_buildings")
    op.drop_index("ix_affordable_lihtc_buildings_id", table_name="affordable_lihtc_buildings")
    op.drop_table("affordable_lihtc_buildings")
