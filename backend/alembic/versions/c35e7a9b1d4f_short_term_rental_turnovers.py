"""Phase 4.12 staff-recorded short-term-rental turnover schedules."""

from alembic import op
import sqlalchemy as sa


revision = "c35e7a9b1d4f"
down_revision = "b24d6f8a0c3e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "short_term_rental_turnovers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="SCHEDULED"),
        sa.Column("cleaning_work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("inspection_record_id", sa.Integer(), sa.ForeignKey("unit_inspection_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "property_id", "unit_id", "scheduled_start",
            name="uq_short_term_rental_turnover_unit_start",
        ),
    )
    op.create_index("ix_short_term_rental_turnovers_organization_id", "short_term_rental_turnovers", ["organization_id"])
    op.create_index("ix_short_term_rental_turnovers_property_id", "short_term_rental_turnovers", ["property_id"])
    op.create_index("ix_short_term_rental_turnovers_unit_id", "short_term_rental_turnovers", ["unit_id"])
    op.create_index("ix_short_term_rental_turnovers_scheduled_start", "short_term_rental_turnovers", ["scheduled_start"])
    op.create_index("ix_short_term_rental_turnovers_scheduled_end", "short_term_rental_turnovers", ["scheduled_end"])
    op.create_index("ix_short_term_rental_turnovers_cleaning_work_order_id", "short_term_rental_turnovers", ["cleaning_work_order_id"])
    op.create_index("ix_short_term_rental_turnovers_inspection_record_id", "short_term_rental_turnovers", ["inspection_record_id"])
    op.create_index(
        "ix_short_term_rental_turnover_scope",
        "short_term_rental_turnovers",
        ["organization_id", "property_id", "unit_id", "scheduled_start", "is_active"],
    )


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled for short-term-rental turnover schedules.")
