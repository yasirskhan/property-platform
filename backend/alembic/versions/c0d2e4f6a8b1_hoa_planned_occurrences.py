"""Persist unissued HOA planning occurrences with unique period keys.

Revision ID: c0d2e4f6a8b1
Revises: b9d1f3a5c7e2
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c0d2e4f6a8b1"
down_revision = "b9d1f3a5c7e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_planned_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("hoa_assessment_proposals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payer_draft_id", sa.Integer(), sa.ForeignKey("hoa_payer_drafts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposed_on", sa.Date(), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("proposal_revision_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PLANNED"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("voided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("voided_at", sa.DateTime()),
        sa.UniqueConstraint("proposal_id", "proposed_on", name="uq_hoa_planned_occurrence_proposal_date"),
    )
    for column in ("organization_id", "association_id", "property_id", "proposal_id", "payer_draft_id"):
        op.create_index(f"ix_hoa_planned_occurrences_{column}", "hoa_planned_occurrences", [column])
    op.create_index("ix_hoa_planned_occurrence_scope", "hoa_planned_occurrences",
                    ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_planned_occurrence_scope", table_name="hoa_planned_occurrences")
    for column in ("payer_draft_id", "proposal_id", "property_id", "association_id", "organization_id"):
        op.drop_index(f"ix_hoa_planned_occurrences_{column}", table_name="hoa_planned_occurrences")
    op.drop_table("hoa_planned_occurrences")
