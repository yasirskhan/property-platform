"""Authorize authenticated HOA board seats and add ARC delivery/follow-up history.

Revision ID: a5c7e9f1b3d6
Revises: a4b6d8f0c2e5
"""
from alembic import op
import sqlalchemy as sa

revision = "a5c7e9f1b3d6"
down_revision = "a4b6d8f0c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hoa_board_seats", sa.Column(
        "authorized_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"),
    ))
    op.add_column("hoa_board_seats", sa.Column(
        "decision_authorized", sa.Boolean(), nullable=False, server_default=sa.text("false"),
    ))
    op.add_column("hoa_board_seats", sa.Column(
        "can_record_offline", sa.Boolean(), nullable=False, server_default=sa.text("false"),
    ))
    op.add_column("hoa_board_seats", sa.Column(
        "authorized_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
    ))
    op.add_column("hoa_board_seats", sa.Column("authorized_at", sa.DateTime()))
    op.create_index(
        "ix_hoa_board_seats_authorized_user_id", "hoa_board_seats", ["authorized_user_id"],
    )
    op.add_column("hoa_arc_decisions", sa.Column(
        "decision_maker_seat_id", sa.Integer(),
        sa.ForeignKey("hoa_board_seats.id", ondelete="RESTRICT"),
    ))
    op.add_column("hoa_arc_decisions", sa.Column("decided_on", sa.Date()))
    op.add_column("hoa_arc_decisions", sa.Column(
        "record_method", sa.String(16), nullable=False, server_default="DIRECT",
    ))
    op.add_column("hoa_arc_decisions", sa.Column(
        "supporting_attachment_id", sa.Integer(),
        sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"),
    ))
    op.add_column("hoa_arc_member_charges", sa.Column(
        "reversal_transaction_id", sa.Integer(),
        sa.ForeignKey("gl_transactions.id", ondelete="RESTRICT"),
    ))
    op.create_index(
        "uq_hoa_arc_member_charge_reversal_gl", "hoa_arc_member_charges",
        ["reversal_transaction_id"], unique=True,
    )
    op.add_column("hoa_arc_member_charges", sa.Column("reversal_reason", sa.Text()))
    op.create_table(
        "hoa_arc_follow_ups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("hoa_arc_decisions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("existing_work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name in ("organization_id", "association_id", "property_id"):
        op.create_index(f"ix_hoa_arc_follow_ups_{name}", "hoa_arc_follow_ups", [name])
    op.create_index(
        "ix_hoa_arc_follow_up_scope", "hoa_arc_follow_ups",
        ["organization_id", "association_id", "property_id"],
    )
    op.create_table(
        "hoa_arc_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("hoa_arc_decisions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name in ("organization_id", "association_id", "property_id"):
        op.create_index(f"ix_hoa_arc_notifications_{name}", "hoa_arc_notifications", [name])
    op.create_index(
        "ix_hoa_arc_notification_scope", "hoa_arc_notifications",
        ["organization_id", "association_id", "property_id"],
    )


def downgrade() -> None:
    for table, composite in (
        ("hoa_arc_notifications", "ix_hoa_arc_notification_scope"),
        ("hoa_arc_follow_ups", "ix_hoa_arc_follow_up_scope"),
    ):
        op.drop_index(composite, table_name=table)
        for name in ("property_id", "association_id", "organization_id"):
            op.drop_index(f"ix_{table}_{name}", table_name=table)
        op.drop_table(table)
    op.drop_column("hoa_arc_member_charges", "reversal_reason")
    op.drop_index(
        "uq_hoa_arc_member_charge_reversal_gl",
        table_name="hoa_arc_member_charges",
    )
    op.drop_column("hoa_arc_member_charges", "reversal_transaction_id")
    for name in (
        "supporting_attachment_id", "record_method", "decided_on",
        "decision_maker_seat_id",
    ):
        op.drop_column("hoa_arc_decisions", name)
    op.drop_index("ix_hoa_board_seats_authorized_user_id", table_name="hoa_board_seats")
    for name in (
        "authorized_at", "authorized_by_id", "can_record_offline",
        "decision_authorized", "authorized_user_id",
    ):
        op.drop_column("hoa_board_seats", name)
