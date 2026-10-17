"""Explicit HOA-to-organization-contact references; not legal membership.

Revision ID: e7a9b1c3d5f8
Revises: d6f8a0b2c4e7
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "e7a9b1c3d5f8"
down_revision = "d6f8a0b2c4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_contact_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", "contact_id", name="uq_hoa_contact_association_property"),
    )
    op.create_index("ix_hoa_contact_links_id", "hoa_contact_links", ["id"])
    op.create_index("ix_hoa_contact_links_organization_id", "hoa_contact_links", ["organization_id"])
    op.create_index("ix_hoa_contact_links_association_id", "hoa_contact_links", ["association_id"])
    op.create_index("ix_hoa_contact_links_property_id", "hoa_contact_links", ["property_id"])
    op.create_index("ix_hoa_contact_links_contact_id", "hoa_contact_links", ["contact_id"])
    op.create_index("ix_hoa_contacts_scope", "hoa_contact_links", ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_contacts_scope", table_name="hoa_contact_links")
    op.drop_index("ix_hoa_contact_links_contact_id", table_name="hoa_contact_links")
    op.drop_index("ix_hoa_contact_links_property_id", table_name="hoa_contact_links")
    op.drop_index("ix_hoa_contact_links_association_id", table_name="hoa_contact_links")
    op.drop_index("ix_hoa_contact_links_organization_id", table_name="hoa_contact_links")
    op.drop_index("ix_hoa_contact_links_id", table_name="hoa_contact_links")
    op.drop_table("hoa_contact_links")
