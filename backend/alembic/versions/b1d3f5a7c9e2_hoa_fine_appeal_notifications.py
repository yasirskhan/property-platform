"""Fine appeal outcome email outbox, separate from accounting and appeal disposition.

Revision ID: b1d3f5a7c9e2
Revises: 6f9e2a7d4c1b
"""
from alembic import op
import sqlalchemy as sa

revision = "b1d3f5a7c9e2"
down_revision = "6f9e2a7d4c1b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_fine_appeal_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False),
        sa.Column("fine_id", sa.Integer(), sa.ForeignKey("hoa_violation_fines.id"), nullable=False),
        sa.Column("appeal_id", sa.Integer(), sa.ForeignKey("hoa_violation_fine_appeals.id"), nullable=False, unique=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("letter_templates.id"), nullable=False),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("subject_snapshot", sa.String(180), nullable=False),
        sa.Column("body_snapshot", sa.Text(), nullable=False),
        sa.Column("outcome_snapshot", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("smtp_accepted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_hoa_appeal_notification_request"),
    )
    op.create_index(
        "ix_hoa_appeal_notification_scope", "hoa_fine_appeal_notifications",
        ["organization_id", "association_id", "property_id", "case_id"],
    )


def downgrade():
    op.drop_index("ix_hoa_appeal_notification_scope", table_name="hoa_fine_appeal_notifications")
    op.drop_table("hoa_fine_appeal_notifications")
