"""Reference private property attachments; no duplicate document bytes.

Revision ID: f0b2c4d6e8a1
Revises: e9a1b3c5d7f0
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa
revision = "f0b2c4d6e8a1"
down_revision = "e9a1b3c5d7f0"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "hoa_governing_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", "attachment_id", name="uq_hoa_evidence_attach"),
    )
    op.create_index("ix_hoa_governing_evidence_id", "hoa_governing_evidence", ["id"])
    op.create_index("ix_hoa_governing_evidence_organization_id", "hoa_governing_evidence", ["organization_id"])
    op.create_index("ix_hoa_governing_evidence_association_id", "hoa_governing_evidence", ["association_id"])
    op.create_index("ix_hoa_governing_evidence_property_id", "hoa_governing_evidence", ["property_id"])
    op.create_index("ix_hoa_governing_evidence_attachment_id", "hoa_governing_evidence", ["attachment_id"])
    op.create_index("ix_hoa_evidence_scope", "hoa_governing_evidence", ["organization_id", "association_id", "property_id"])

def downgrade() -> None:
    op.drop_index("ix_hoa_evidence_scope", table_name="hoa_governing_evidence")
    for name in ("attachment_id", "property_id", "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_governing_evidence_{name}", table_name="hoa_governing_evidence")
    op.drop_table("hoa_governing_evidence")
