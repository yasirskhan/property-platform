"""Staff HOA association/property registry only; no finance or board actions.

Revision ID: d6f8a0b2c4e7
Revises: c5e7a9b1d3f6
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "d6f8a0b2c4e7"
down_revision = "c5e7a9b1d3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_associations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("name_key", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "name_key", name="uq_hoa_assoc_org_name"),
    )
    op.create_index("ix_hoa_associations_id", "hoa_associations", ["id"])
    op.create_index("ix_hoa_associations_organization_id", "hoa_associations", ["organization_id"])
    op.create_table(
        "hoa_property_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", name="uq_hoa_membership_assoc_property"),
    )
    op.create_index("ix_hoa_property_memberships_id", "hoa_property_memberships", ["id"])
    op.create_index("ix_hoa_property_memberships_organization_id", "hoa_property_memberships", ["organization_id"])
    op.create_index("ix_hoa_property_memberships_association_id", "hoa_property_memberships", ["association_id"])
    op.create_index("ix_hoa_property_memberships_property_id", "hoa_property_memberships", ["property_id"])
    op.create_index("ix_hoa_member_org_assoc", "hoa_property_memberships", ["organization_id", "association_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_member_org_assoc", table_name="hoa_property_memberships")
    op.drop_index("ix_hoa_property_memberships_property_id", table_name="hoa_property_memberships")
    op.drop_index("ix_hoa_property_memberships_association_id", table_name="hoa_property_memberships")
    op.drop_index("ix_hoa_property_memberships_organization_id", table_name="hoa_property_memberships")
    op.drop_index("ix_hoa_property_memberships_id", table_name="hoa_property_memberships")
    op.drop_table("hoa_property_memberships")
    op.drop_index("ix_hoa_associations_organization_id", table_name="hoa_associations")
    op.drop_index("ix_hoa_associations_id", table_name="hoa_associations")
    op.drop_table("hoa_associations")
