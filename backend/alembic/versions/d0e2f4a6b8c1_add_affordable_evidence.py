"""Property-program evidence-index readiness, not compliance certification.

Revision ID: d0e2f4a6b8c1
Revises: c9d1e3f5a7b0
"""
from alembic import op
import sqlalchemy as sa

revision = "d0e2f4a6b8c1"
down_revision = "c9d1e3f5a7b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_program_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("staff_follow_up_on", sa.Date(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["affordable_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "program_id", "category",
                            name="uq_affordable_evidence_category"),
    )
    op.create_index("ix_affordable_program_evidence_id", "affordable_program_evidence", ["id"])
    op.create_index("ix_affordable_program_evidence_organization_id", "affordable_program_evidence", ["organization_id"])
    op.create_index("ix_affordable_program_evidence_program_id", "affordable_program_evidence", ["program_id"])
    op.create_index("ix_affordable_evidence_scope", "affordable_program_evidence", ["organization_id", "program_id"])


def downgrade() -> None:
    op.drop_index("ix_affordable_evidence_scope", table_name="affordable_program_evidence")
    op.drop_index("ix_affordable_program_evidence_program_id", table_name="affordable_program_evidence")
    op.drop_index("ix_affordable_program_evidence_organization_id", table_name="affordable_program_evidence")
    op.drop_index("ix_affordable_program_evidence_id", table_name="affordable_program_evidence")
    op.drop_table("affordable_program_evidence")
