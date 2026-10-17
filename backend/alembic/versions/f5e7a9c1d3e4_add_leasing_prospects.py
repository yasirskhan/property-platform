"""Phase 4 leasing CRM: contacts as leads, scoped to property.

Revision ID: f5e7a9c1d3e4
Revises: f4e6a8c0d2e3
"""
from alembic import op
import sqlalchemy as sa
revision = "f5e7a9c1d3e4"
down_revision = "f4e6a8c0d2e3"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "leasing_prospects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("next_follow_up", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_leasing_prospects_id","leasing_prospects",["id"])
    op.create_index("ix_leasing_prospects_organization_id","leasing_prospects",["organization_id"])
    op.create_index("ix_leasing_prospects_property_id","leasing_prospects",["property_id"])
    op.create_index("ix_leasing_prospects_contact_id","leasing_prospects",["contact_id"])
    op.create_index("ix_leasing_prospects_org_property_stage","leasing_prospects",["organization_id","property_id","stage"])

def downgrade():
    op.drop_index("ix_leasing_prospects_org_property_stage", table_name="leasing_prospects")
    op.drop_index("ix_leasing_prospects_contact_id", table_name="leasing_prospects")
    op.drop_index("ix_leasing_prospects_property_id", table_name="leasing_prospects")
    op.drop_index("ix_leasing_prospects_organization_id", table_name="leasing_prospects")
    op.drop_index("ix_leasing_prospects_id", table_name="leasing_prospects")
    op.drop_table("leasing_prospects")
