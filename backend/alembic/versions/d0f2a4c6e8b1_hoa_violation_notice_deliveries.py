"""Association-authorized violation correspondence email attempt history.

Revision ID: d0f2a4c6e8b1
Revises: c9e1f3b5d7a0
"""
from alembic import op
import sqlalchemy as sa

revision = "d0f2a4c6e8b1"
down_revision = "c9e1f3b5d7a0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_violation_notice_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False),
        sa.Column("correspondence_id", sa.Integer(), sa.ForeignKey("hoa_violation_correspondence_drafts.id"), nullable=False, unique=True),
        sa.Column("correspondence_revision", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("hoa_procedure_policies.id"), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("smtp_accepted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_hoa_violation_delivery_request"),
    )
    op.create_index(
        "ix_hoa_violation_delivery_scope", "hoa_violation_notice_deliveries",
        ["organization_id", "association_id", "property_id", "case_id"],
    )


def downgrade():
    op.drop_index("ix_hoa_violation_delivery_scope", table_name="hoa_violation_notice_deliveries")
    op.drop_table("hoa_violation_notice_deliveries")
