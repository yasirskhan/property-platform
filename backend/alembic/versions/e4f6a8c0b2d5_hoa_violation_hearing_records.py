"""Standalone violation hearing outcome record.

Revision ID: e4f6a8c0b2d5
Revises: d9f1b3c5e7a2
"""
from alembic import op
import sqlalchemy as sa
revision = "e4f6a8c0b2d5"
down_revision = "d9f1b3c5e7a2"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "hoa_violation_hearing_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id"), nullable=False),
        sa.Column("service_record_id", sa.Integer(), sa.ForeignKey("hoa_violation_service_records.id"), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("member_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id"), nullable=False),
        sa.Column("disposition", sa.String(32), nullable=False),
        sa.Column("held_on", sa.Date(), nullable=True),
        sa.Column("record_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id"), nullable=True),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", name="uq_hoa_hearing_case"),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_hoa_hearing_request"),
        sa.CheckConstraint(
            "(disposition = 'HEARING_HELD' AND held_on IS NOT NULL AND record_attachment_id IS NOT NULL) OR "
            "(disposition = 'NO_REQUEST_RECORDED' AND held_on IS NULL AND record_attachment_id IS NULL)",
            name="ck_hoa_hearing_coherent",
        ),
    )
    op.create_index("ix_hoa_hearing_scope", "hoa_violation_hearing_records",
                    ["organization_id", "association_id", "property_id", "case_id"])
    with op.batch_alter_table("hoa_violation_fines") as batch:
        batch.add_column(sa.Column("hearing_record_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_hoa_violation_fine_hearing_record",
            "hoa_violation_hearing_records", ["hearing_record_id"], ["id"], ondelete="RESTRICT")

def downgrade():
    with op.batch_alter_table("hoa_violation_fines") as batch:
        batch.drop_constraint("fk_hoa_violation_fine_hearing_record", type_="foreignkey")
        batch.drop_column("hearing_record_id")
    op.drop_index("ix_hoa_hearing_scope", table_name="hoa_violation_hearing_records")
    op.drop_table("hoa_violation_hearing_records")
