"""Property-level staff-recorded affordable program inventory.

Revision ID: b8c0d2e4f6a9
Revises: a7c9e1f3b5d0
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c0d2e4f6a9"
down_revision = "a7c9e1f3b5d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("program_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("agency_name", sa.String(length=160), nullable=True),
        sa.Column("recorded_start", sa.Date(), nullable=True),
        sa.Column("recorded_end", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "property_id", "label", name="uq_affordable_program_property_label"),
    )
    op.create_index("ix_affordable_programs_id", "affordable_programs", ["id"], unique=False)
    op.create_index("ix_affordable_programs_organization_id", "affordable_programs", ["organization_id"], unique=False)
    op.create_index("ix_affordable_programs_property_id", "affordable_programs", ["property_id"], unique=False)
    op.create_index("ix_affordable_program_scope", "affordable_programs", ["organization_id", "property_id", "is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_affordable_program_scope", table_name="affordable_programs")
    op.drop_index("ix_affordable_programs_property_id", table_name="affordable_programs")
    op.drop_index("ix_affordable_programs_organization_id", table_name="affordable_programs")
    op.drop_index("ix_affordable_programs_id", table_name="affordable_programs")
    op.drop_table("affordable_programs")
