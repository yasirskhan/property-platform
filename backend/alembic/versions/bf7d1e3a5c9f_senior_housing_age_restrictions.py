"""Phase 4.11 senior-housing age-restriction foundation."""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "bf7d1e3a5c9f"
down_revision = "ae6c8d0f2b4c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "senior_age_restrictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("restriction_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("minimum_age", sa.Integer(), nullable=True),
        sa.Column("recorded_authority", sa.String(length=180), nullable=True),
        sa.Column("reference_identifier", sa.String(length=180), nullable=True),
        sa.Column("effective_start", sa.Date(), nullable=True),
        sa.Column("effective_end", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "property_id", "label", name="uq_senior_age_restriction_property_label"),
    )
    op.create_index("ix_senior_age_restrictions_organization_id", "senior_age_restrictions", ["organization_id"])
    op.create_index("ix_senior_age_restrictions_property_id", "senior_age_restrictions", ["property_id"])
    op.create_index("ix_senior_age_restriction_scope", "senior_age_restrictions", ["organization_id", "property_id", "is_active"])

    gate = sa.table(
        "release_gates",
        sa.column("key", sa.String()),
        sa.column("stage", sa.String()),
        sa.column("description", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    now = datetime.utcnow()
    op.bulk_insert(gate, [{
        "key": "release.properties.senior_housing",
        "stage": "HIDDEN",
        "description": "Senior housing age-restriction, care coordination and HUD 202/811 workflows",
        "created_at": now,
        "updated_at": now,
    }])


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled for senior-housing compliance records.")
