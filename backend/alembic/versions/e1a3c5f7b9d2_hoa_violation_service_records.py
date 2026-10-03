"""Association-reported notice service with private proof, not automatic statutory certification.

Revision ID: e1a3c5f7b9d2
Revises: d0f2a4c6e8b1
"""
from alembic import op
import sqlalchemy as sa

revision = "e1a3c5f7b9d2"
down_revision = "d0f2a4c6e8b1"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "hoa_violation_service_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False, unique=True),
        sa.Column("correspondence_id", sa.Integer(), sa.ForeignKey("hoa_violation_correspondence_drafts.id"), nullable=False),
        sa.Column("correspondence_revision", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id"), nullable=False),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("service_proof_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id"), nullable=False),
        sa.Column("delivery_method", sa.String(24), nullable=False),
        sa.Column("served_on", sa.Date(), nullable=False),
        sa.Column("cure_earliest_on", sa.Date(), nullable=False),
        sa.Column("hearing_request_earliest_on", sa.Date(), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_hoa_service_request"),
    )
    op.create_index("ix_hoa_service_scope", "hoa_violation_service_records",
        ["organization_id", "association_id", "property_id", "case_id"])

def downgrade():
    op.drop_index("ix_hoa_service_scope", table_name="hoa_violation_service_records")
    op.drop_table("hoa_violation_service_records")
