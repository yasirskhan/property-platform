"""Add immutable staff-only violation correspondence drafts.

Revision ID: c7e9f1a3b5d8
Revises: f4b6d8a0c2e9
"""
from alembic import op
import sqlalchemy as sa

revision = "c7e9f1a3b5d8"
down_revision = "f4b6d8a0c2e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_violation_correspondence_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("hoa_procedure_policies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("recipient_reference_id", sa.Integer(), sa.ForeignKey("hoa_violation_recipient_drafts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("matched_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("draft_notice_on", sa.Date(), nullable=True),
        sa.Column("tentative_cure_on", sa.Date(), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("prepared_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("prepared_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", "revision", name="uq_hoa_violation_draft_case_revision"),
    )
    for name in ("organization_id", "association_id", "property_id", "case_id"):
        op.create_index("ix_hoa_violation_correspondence_drafts_" + name,
                        "hoa_violation_correspondence_drafts", [name])
    op.create_index("ix_hoa_violation_draft_scope",
                    "hoa_violation_correspondence_drafts",
                    ["organization_id", "association_id", "property_id", "case_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_violation_draft_scope", table_name="hoa_violation_correspondence_drafts")
    for name in ("case_id", "property_id", "association_id", "organization_id"):
        op.drop_index("ix_hoa_violation_correspondence_drafts_" + name,
                      table_name="hoa_violation_correspondence_drafts")
    op.drop_table("hoa_violation_correspondence_drafts")
