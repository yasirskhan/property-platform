"""Staff ARC intake only. No approval, permit or fee.

Revision ID: e9a1b3c5d7f0
Revises: d8f0a2b4c6e9
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "e9a1b3c5d7f0"
down_revision = "d8f0a2b4c6e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_arc_intakes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_title", sa.String(length=140), nullable=False),
        sa.Column("staff_noted_on", sa.Date(), nullable=False),
        sa.Column("staff_description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hoa_arc_intakes_id", "hoa_arc_intakes", ["id"])
    op.create_index("ix_hoa_arc_intakes_organization_id", "hoa_arc_intakes", ["organization_id"])
    op.create_index("ix_hoa_arc_intakes_association_id", "hoa_arc_intakes", ["association_id"])
    op.create_index("ix_hoa_arc_intakes_property_id", "hoa_arc_intakes", ["property_id"])
    op.create_index("ix_hoa_arc_intake_scope", "hoa_arc_intakes", ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_arc_intake_scope", table_name="hoa_arc_intakes")
    op.drop_index("ix_hoa_arc_intakes_property_id", table_name="hoa_arc_intakes")
    op.drop_index("ix_hoa_arc_intakes_association_id", table_name="hoa_arc_intakes")
    op.drop_index("ix_hoa_arc_intakes_organization_id", table_name="hoa_arc_intakes")
    op.drop_index("ix_hoa_arc_intakes_id", table_name="hoa_arc_intakes")
    op.drop_table("hoa_arc_intakes")
