"""Add manually sourced 1099 preparation review records.

Revision ID: e7b9c1d3f5a8
Revises: d6a8b0c2e4f7
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "e7b9c1d3f5a8"
down_revision = "d6a8b0c2e4f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_1099_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("form_type", sa.String(length=16), nullable=False),
        sa.Column("income_category", sa.String(length=48), nullable=False),
        sa.Column("payer_profile_id", sa.Integer(), nullable=False),
        sa.Column("recipient_profile_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=160), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PREPARED"),
        sa.Column("source_review_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("threshold_review_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recipient_review_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("prepared_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payer_profile_id"], ["tax_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_profile_id"], ["tax_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prepared_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_tax_1099_review_idempotency"),
    )
    op.create_index("ix_tax_1099_reviews_id", "tax_1099_reviews", ["id"], unique=False)
    op.create_index("ix_tax_1099_reviews_organization_id", "tax_1099_reviews", ["organization_id"], unique=False)
    op.create_index("ix_tax_1099_reviews_tax_year", "tax_1099_reviews", ["tax_year"], unique=False)
    op.create_index("ix_tax_1099_reviews_payer_profile_id", "tax_1099_reviews", ["payer_profile_id"], unique=False)
    op.create_index("ix_tax_1099_reviews_recipient_profile_id", "tax_1099_reviews", ["recipient_profile_id"], unique=False)
    op.create_index("ix_tax_1099_reviews_status", "tax_1099_reviews", ["status"], unique=False)
    op.create_index("ix_tax_1099_review_scope", "tax_1099_reviews", ["organization_id", "tax_year", "status", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tax_1099_review_scope", table_name="tax_1099_reviews")
    op.drop_index("ix_tax_1099_reviews_status", table_name="tax_1099_reviews")
    op.drop_index("ix_tax_1099_reviews_recipient_profile_id", table_name="tax_1099_reviews")
    op.drop_index("ix_tax_1099_reviews_payer_profile_id", table_name="tax_1099_reviews")
    op.drop_index("ix_tax_1099_reviews_tax_year", table_name="tax_1099_reviews")
    op.drop_index("ix_tax_1099_reviews_organization_id", table_name="tax_1099_reviews")
    op.drop_index("ix_tax_1099_reviews_id", table_name="tax_1099_reviews")
    op.drop_table("tax_1099_reviews")
