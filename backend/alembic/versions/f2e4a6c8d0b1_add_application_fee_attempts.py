"""One scoped application fee preparation per rental application.

Revision ID: f2e4a6c8d0b1
Revises: f1e3a5c7d9b0
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "f2e4a6c8d0b1"
down_revision = "f1e3a5c7d9b0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "application_fee_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("applicant_user_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["lease_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["applicant_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_application_fee_attempt_application"),
    )
    op.create_index("ix_application_fee_attempts_id", "application_fee_attempts", ["id"])
    op.create_index("ix_application_fee_attempts_organization_id", "application_fee_attempts", ["organization_id"])
    op.create_index("ix_application_fee_attempts_application_id", "application_fee_attempts", ["application_id"])


def downgrade():
    op.drop_index("ix_application_fee_attempts_application_id", table_name="application_fee_attempts")
    op.drop_index("ix_application_fee_attempts_organization_id", table_name="application_fee_attempts")
    op.drop_index("ix_application_fee_attempts_id", table_name="application_fee_attempts")
    op.drop_table("application_fee_attempts")
