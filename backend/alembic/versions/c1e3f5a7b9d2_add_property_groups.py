"""Persist explicit named property groups and membership, no inferred grouping.

Revision ID: c1e3f5a7b9d2
Revises: b0d2f4a6c8e1
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "c1e3f5a7b9d2"
down_revision = "b0d2f4a6c8e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("name_key", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name_key", name="uq_property_group_org_name"),
    )
    op.create_index("ix_property_groups_id", "property_groups", ["id"], unique=False)
    op.create_index("ix_property_groups_organization_id", "property_groups", ["organization_id"], unique=False)
    op.create_table(
        "property_group_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["property_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "property_id", name="uq_property_group_member"),
    )
    op.create_index("ix_property_group_memberships_id", "property_group_memberships", ["id"], unique=False)
    op.create_index("ix_property_group_memberships_organization_id", "property_group_memberships", ["organization_id"], unique=False)
    op.create_index("ix_property_group_memberships_group_id", "property_group_memberships", ["group_id"], unique=False)
    op.create_index("ix_property_group_memberships_property_id", "property_group_memberships", ["property_id"], unique=False)
    op.create_index("ix_pg_membership_org_group", "property_group_memberships", ["organization_id", "group_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pg_membership_org_group", table_name="property_group_memberships")
    for name in ("property_id", "group_id", "organization_id", "id"):
        op.drop_index(f"ix_property_group_memberships_{name}", table_name="property_group_memberships")
    op.drop_table("property_group_memberships")
    op.drop_index("ix_property_groups_organization_id", table_name="property_groups")
    op.drop_index("ix_property_groups_id", table_name="property_groups")
    op.drop_table("property_groups")
