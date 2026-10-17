"""Staff-only per-building Form 8609 reference readiness.

Revision ID: f2a4b6c8d0e3
Revises: e1f3a5b7c9d2
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a4b6c8d0e3"
down_revision = "e1f3a5b7c9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_lihtc_8609_readiness",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["affordable_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["building_id"], ["affordable_lihtc_buildings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "building_id", name="uq_lihtc_8609_building"),
    )
    op.create_index("ix_affordable_lihtc_8609_readiness_id", "affordable_lihtc_8609_readiness", ["id"])
    op.create_index("ix_affordable_lihtc_8609_readiness_organization_id", "affordable_lihtc_8609_readiness", ["organization_id"])
    op.create_index("ix_affordable_lihtc_8609_readiness_property_id", "affordable_lihtc_8609_readiness", ["property_id"])
    op.create_index("ix_affordable_lihtc_8609_readiness_program_id", "affordable_lihtc_8609_readiness", ["program_id"])
    op.create_index("ix_affordable_lihtc_8609_readiness_building_id", "affordable_lihtc_8609_readiness", ["building_id"])
    op.create_index("ix_lihtc_8609_scope", "affordable_lihtc_8609_readiness",
                    ["organization_id", "property_id", "program_id", "building_id"])


def downgrade() -> None:
    op.drop_index("ix_lihtc_8609_scope", table_name="affordable_lihtc_8609_readiness")
    for name in ("building_id", "program_id", "property_id", "organization_id", "id"):
        op.drop_index(f"ix_affordable_lihtc_8609_readiness_{name}", table_name="affordable_lihtc_8609_readiness")
    op.drop_table("affordable_lihtc_8609_readiness")
