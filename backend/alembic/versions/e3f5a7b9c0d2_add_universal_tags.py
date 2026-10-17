"""Org tag vocabulary and audited explicit entity references.

Revision ID: e3f5a7b9c0d2
Revises: d2e4f6a8b0c1
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f5a7b9c0d2"
down_revision = "d2e4f6a8b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "normalized_name", name="uq_tag_org_normalized_name"),
    )
    op.create_index("ix_tags_id", "tags", ["id"], unique=False)
    op.create_index("ix_tags_organization_id", "tags", ["organization_id"], unique=False)

    op.create_table(
        "entity_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "tag_id", "entity_type", "entity_id", name="uq_entity_tag_scope"),
    )
    op.create_index("ix_entity_tags_id", "entity_tags", ["id"], unique=False)
    op.create_index("ix_entity_tags_organization_id", "entity_tags", ["organization_id"], unique=False)
    op.create_index("ix_entity_tags_tag_id", "entity_tags", ["tag_id"], unique=False)
    op.create_index("ix_entity_tags_target", "entity_tags", ["organization_id", "entity_type", "entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_entity_tags_target", table_name="entity_tags")
    op.drop_index("ix_entity_tags_tag_id", table_name="entity_tags")
    op.drop_index("ix_entity_tags_organization_id", table_name="entity_tags")
    op.drop_index("ix_entity_tags_id", table_name="entity_tags")
    op.drop_table("entity_tags")
    op.drop_index("ix_tags_organization_id", table_name="tags")
    op.drop_index("ix_tags_id", table_name="tags")
    op.drop_table("tags")
