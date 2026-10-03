"""add universal entity notes

Revision ID: f2c4e6a8b0d3
Revises: e1b3d5f7a9c2
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa


revision = "f2c4e6a8b0d3"
down_revision = "e1b3d5f7a9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_notes_id", "entity_notes", ["id"], unique=False)
    op.create_index("ix_entity_notes_organization_id", "entity_notes", ["organization_id"], unique=False)
    op.create_index("ix_entity_notes_entity_type", "entity_notes", ["entity_type"], unique=False)
    op.create_index("ix_entity_notes_entity_id", "entity_notes", ["entity_id"], unique=False)
    op.create_index("ix_entity_notes_created_by_id", "entity_notes", ["created_by_id"], unique=False)
    op.create_index("ix_entity_notes_created_at", "entity_notes", ["created_at"], unique=False)
    op.create_index(
        "ix_entity_notes_target",
        "entity_notes",
        ["organization_id", "entity_type", "entity_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_entity_notes_target", table_name="entity_notes")
    op.drop_index("ix_entity_notes_created_at", table_name="entity_notes")
    op.drop_index("ix_entity_notes_created_by_id", table_name="entity_notes")
    op.drop_index("ix_entity_notes_entity_id", table_name="entity_notes")
    op.drop_index("ix_entity_notes_entity_type", table_name="entity_notes")
    op.drop_index("ix_entity_notes_organization_id", table_name="entity_notes")
    op.drop_index("ix_entity_notes_id", table_name="entity_notes")
    op.drop_table("entity_notes")
