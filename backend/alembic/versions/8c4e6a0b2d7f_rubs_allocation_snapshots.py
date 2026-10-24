from alembic import op
import sqlalchemy as sa


revision = "8c4e6a0b2d7f"
down_revision = "7b3d9f1a5c2e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "utility_allocation_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utility_id", sa.Integer(), sa.ForeignKey("property_utilities.id"), nullable=False),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("utility_bills.id"), nullable=False),
        sa.Column(
            "rule_revision_id",
            sa.Integer(),
            sa.ForeignKey("utility_allocation_rule_revisions.id"),
            nullable=False,
        ),
        sa.Column("billing_period_start", sa.Date(), nullable=False),
        sa.Column("billing_period_end", sa.Date(), nullable=False),
        sa.Column("bill_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("basis", sa.String(length=32), nullable=False),
        sa.Column("unit_inputs_json", sa.Text(), nullable=False),
        sa.Column("allocation_items_json", sa.Text(), nullable=False),
        sa.Column("allocated_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("remainder_rule", sa.Text(), nullable=False),
        sa.Column("request_key", sa.String(length=96), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "utility_id",
            "request_key",
            name="uq_utility_allocation_snapshot_request",
        ),
    )
    op.create_index(
        "ix_utility_allocation_snapshots_utility_id",
        "utility_allocation_snapshots",
        ["utility_id"],
    )
    op.create_index(
        "ix_utility_allocation_snapshots_bill_id",
        "utility_allocation_snapshots",
        ["bill_id"],
    )
    op.create_index(
        "ix_utility_allocation_snapshots_rule_revision_id",
        "utility_allocation_snapshots",
        ["rule_revision_id"],
    )
    op.create_index(
        "ix_utility_allocation_snapshots_billing_period_start",
        "utility_allocation_snapshots",
        ["billing_period_start"],
    )
    op.create_index(
        "ix_utility_allocation_snapshots_billing_period_end",
        "utility_allocation_snapshots",
        ["billing_period_end"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for reviewed RUBs allocation snapshots."
    )
