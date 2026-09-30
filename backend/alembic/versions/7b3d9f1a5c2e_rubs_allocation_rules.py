from alembic import op
import sqlalchemy as sa
revision = "7b3d9f1a5c2e"
down_revision = "e6f8a0c2d4b7"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table(
        "utility_allocation_rule_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utility_id", sa.Integer(), sa.ForeignKey("property_utilities.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("basis", sa.String(length=32), nullable=False),
        sa.Column("unit_inputs_json", sa.Text(), nullable=False),
        sa.Column("request_key", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("is_authorized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("authorization_request_key", sa.String(length=96), nullable=True),
        sa.Column("authorized_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("authorized_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("utility_id", "revision_number", name="uq_utility_allocation_rule_revision"),
        sa.UniqueConstraint("utility_id", "request_key", name="uq_utility_allocation_rule_request"),
    )
    op.create_index("ix_utility_allocation_rule_revisions_utility_id", "utility_allocation_rule_revisions", ["utility_id"])
    op.create_index("ix_utility_allocation_rule_revisions_effective_date", "utility_allocation_rule_revisions", ["effective_date"])
def downgrade():
    pass
