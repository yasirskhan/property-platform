"""Association fine appeal history.

Revision ID: 6f9e2a7d4c1b
Revises: c8e0a2f4b6d9
"""
from alembic import op
import sqlalchemy as sa

revision = "6f9e2a7d4c1b"
down_revision = "c8e0a2f4b6d9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_violation_fine_appeals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False),
        sa.Column("fine_id", sa.Integer(), sa.ForeignKey("hoa_violation_fines.id"), nullable=False),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("appeal_reason", sa.Text(), nullable=False),
        sa.Column("supporting_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id")),
        sa.Column("received_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="OPEN"),
        sa.Column("decided_on", sa.Date()),
        sa.Column("decision_note", sa.Text()),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("decision_board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id")),
        sa.Column("decision_request_key", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_hoa_fine_appeal_request"),
        sa.UniqueConstraint("organization_id", "decision_request_key", name="uq_hoa_fine_appeal_decision_request"),
    )


def downgrade():
    op.drop_table("hoa_violation_fine_appeals")
