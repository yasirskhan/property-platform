"""Private HOA violation case evidence links.

Revision ID: d8f0a2c4e6b9
Revises: c7e9f1a3b5d8
"""
from alembic import op
import sqlalchemy as sa

revision = "d8f0a2c4e6b9"
down_revision = "c7e9f1a3b5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_violation_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_type", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("archived_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime()),
        sa.UniqueConstraint("case_id", "attachment_id", name="uq_hoa_violation_evidence_case_attachment"),
    )
    for name in ("organization_id", "association_id", "property_id", "case_id", "attachment_id"):
        op.create_index("ix_hoa_violation_evidence_" + name,
                        "hoa_violation_evidence", [name])
    op.create_index("ix_hoa_violation_evidence_scope",
                    "hoa_violation_evidence",
                    ["organization_id", "association_id", "property_id", "case_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_violation_evidence_scope", table_name="hoa_violation_evidence")
    for name in ("attachment_id", "case_id", "property_id", "association_id", "organization_id"):
        op.drop_index("ix_hoa_violation_evidence_" + name,
                      table_name="hoa_violation_evidence")
    op.drop_table("hoa_violation_evidence")
