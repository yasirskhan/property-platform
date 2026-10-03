"""Email delivery audit/outbox for existing scoped HOA documents.

Revision ID: f0b2d4e6a8c1
Revises: e9a1c3f5b7d0
"""
from alembic import op
import sqlalchemy as sa

revision = "f0b2d4e6a8c1"
down_revision = "e9a1c3f5b7d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_document_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("hoa_governing_evidence.id"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("accepted_at", sa.DateTime()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", "request_key", name="uq_hoa_doc_delivery_request"),
    )
    op.create_index("ix_hoa_doc_delivery_scope", "hoa_document_deliveries", ["organization_id", "association_id", "property_id"])


def downgrade():
    op.drop_index("ix_hoa_doc_delivery_scope", table_name="hoa_document_deliveries")
    op.drop_table("hoa_document_deliveries")
