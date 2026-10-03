"""Add organization-scoped lease drafts and ordered addenda.

Revision ID: f4e6a8c0d2e3
Revises: f3e5a7c9d1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "f4e6a8c0d2e3"
down_revision = "f3e5a7c9d1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lease_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_lease_templates_id", "lease_templates", ["id"])
    op.create_index("ix_lease_templates_organization_id", "lease_templates", ["organization_id"])
    op.create_index("ix_lease_templates_property_id", "lease_templates", ["property_id"])
    op.create_index("ix_lease_templates_scope", "lease_templates", ["organization_id", "property_id", "is_active"])
    op.create_table(
        "lease_template_addenda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("lease_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_lease_template_addenda_id", "lease_template_addenda", ["id"])
    op.create_index("ix_lease_template_addenda_template_id", "lease_template_addenda", ["template_id"])
    op.create_index("ix_lease_template_addenda_organization_id", "lease_template_addenda", ["organization_id"])
    op.create_index("ix_lease_addenda_template", "lease_template_addenda", ["organization_id", "template_id", "position"])


def downgrade():
    op.drop_index("ix_lease_addenda_template", table_name="lease_template_addenda")
    op.drop_index("ix_lease_template_addenda_organization_id", table_name="lease_template_addenda")
    op.drop_index("ix_lease_template_addenda_template_id", table_name="lease_template_addenda")
    op.drop_index("ix_lease_template_addenda_id", table_name="lease_template_addenda")
    op.drop_table("lease_template_addenda")
    op.drop_index("ix_lease_templates_scope", table_name="lease_templates")
    op.drop_index("ix_lease_templates_property_id", table_name="lease_templates")
    op.drop_index("ix_lease_templates_organization_id", table_name="lease_templates")
    op.drop_index("ix_lease_templates_id", table_name="lease_templates")
    op.drop_table("lease_templates")
