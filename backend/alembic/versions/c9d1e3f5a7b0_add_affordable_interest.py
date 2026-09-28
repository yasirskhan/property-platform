"""Staff-recorded affordable program CRM interest, not an official waitlist.

Revision ID: c9d1e3f5a7b0
Revises: b8c0d2e4f6a9
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d1e3f5a7b0"
down_revision = "b8c0d2e4f6a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_program_interests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("prospect_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("recorded_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["affordable_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospect_id"], ["leasing_prospects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "program_id", "prospect_id", name="uq_affordable_interest_org_program_prospect"),
    )
    op.create_index("ix_affordable_program_interests_id", "affordable_program_interests", ["id"])
    op.create_index("ix_affordable_program_interests_organization_id", "affordable_program_interests", ["organization_id"])
    op.create_index("ix_affordable_program_interests_program_id", "affordable_program_interests", ["program_id"])
    op.create_index("ix_affordable_program_interests_prospect_id", "affordable_program_interests", ["prospect_id"])
    op.create_index("ix_affordable_interest_org_program_active", "affordable_program_interests", ["organization_id", "program_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_affordable_interest_org_program_active", table_name="affordable_program_interests")
    op.drop_index("ix_affordable_program_interests_prospect_id", table_name="affordable_program_interests")
    op.drop_index("ix_affordable_program_interests_program_id", table_name="affordable_program_interests")
    op.drop_index("ix_affordable_program_interests_organization_id", table_name="affordable_program_interests")
    op.drop_index("ix_affordable_program_interests_id", table_name="affordable_program_interests")
    op.drop_table("affordable_program_interests")
