"""Phase 4.11 staff-recorded HUD 202/811 program/readiness facts."""
from alembic import op
import sqlalchemy as sa


revision = "d19f3a5c7e2b"
down_revision = "c08e2f4a6d1b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "senior_hud_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("recorded_authority", sa.String(length=180), nullable=True),
        sa.Column("reference_identifier", sa.String(length=180), nullable=True),
        sa.Column("readiness_status", sa.String(length=32), nullable=False, server_default="REFERENCE_ONLY"),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("effective_start", sa.Date(), nullable=True),
        sa.Column("effective_end", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "property_id",
            "program_type",
            "label",
            name="uq_senior_hud_program_property_type_label",
        ),
    )
    op.create_index("ix_senior_hud_programs_organization_id", "senior_hud_programs", ["organization_id"])
    op.create_index("ix_senior_hud_programs_property_id", "senior_hud_programs", ["property_id"])
    op.create_index(
        "ix_senior_hud_program_scope",
        "senior_hud_programs",
        ["organization_id", "property_id", "is_active"],
    )


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled for senior-housing HUD program records.")
