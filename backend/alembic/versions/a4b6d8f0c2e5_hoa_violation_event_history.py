from alembic import op
import sqlalchemy as sa

revision = "a4b6d8f0c2e5"
down_revision = "f3a5c7e9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_violation_case_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(32)),
        sa.Column("to_stage", sa.String(32), nullable=False),
        sa.Column("policy_revision", sa.Integer()),
        sa.Column("staff_action_on", sa.Date()),
        sa.Column("tentative_cure_on", sa.Date()),
        sa.Column("tentative_hearing_on", sa.Date()),
        sa.Column("proposed_fine", sa.Numeric(14, 2)),
        sa.Column("staff_resolution", sa.Text()),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    for field in ("organization_id", "association_id", "property_id", "case_id"):
        op.create_index("ix_hoa_violation_case_events_" + field, "hoa_violation_case_events", [field])
    op.create_index("ix_hoa_violation_event_scope", "hoa_violation_case_events", [
        "organization_id", "association_id", "property_id", "case_id", "id",
    ])


def downgrade() -> None:
    op.drop_index("ix_hoa_violation_event_scope", table_name="hoa_violation_case_events")
    for field in ("case_id", "property_id", "association_id", "organization_id"):
        op.drop_index("ix_hoa_violation_case_events_" + field, table_name="hoa_violation_case_events")
    op.drop_table("hoa_violation_case_events")
