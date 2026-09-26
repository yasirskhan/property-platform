"""add universal entity attachments

Revision ID: a3d5f7b9c1e4
Revises: f2c4e6a8b0d3
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa


revision = "a3d5f7b9c1e4"
down_revision = "f2c4e6a8b0d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("share_with_tenants", sa.Boolean(), nullable=False),
        sa.Column("share_with_owners", sa.Boolean(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_entity_attachments_id", "entity_attachments", ["id"], unique=False)
    op.create_index("ix_entity_attachments_organization_id", "entity_attachments", ["organization_id"], unique=False)
    op.create_index("ix_entity_attachments_entity_type", "entity_attachments", ["entity_type"], unique=False)
    op.create_index("ix_entity_attachments_entity_id", "entity_attachments", ["entity_id"], unique=False)
    op.create_index("ix_entity_attachments_storage_key", "entity_attachments", ["storage_key"], unique=True)
    op.create_index("ix_entity_attachments_uploaded_by_id", "entity_attachments", ["uploaded_by_id"], unique=False)
    op.create_index("ix_entity_attachments_is_active", "entity_attachments", ["is_active"], unique=False)
    op.create_index("ix_entity_attachments_created_at", "entity_attachments", ["created_at"], unique=False)
    op.create_index(
        "ix_entity_attachments_target",
        "entity_attachments",
        ["organization_id", "entity_type", "entity_id", "is_active", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_entity_attachments_target", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_created_at", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_is_active", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_uploaded_by_id", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_storage_key", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_entity_id", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_entity_type", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_organization_id", table_name="entity_attachments")
    op.drop_index("ix_entity_attachments_id", table_name="entity_attachments")
    op.drop_table("entity_attachments")
