from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "9d5f7b1c3e8a"
down_revision = "8c4e6a0b2d7f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_academic_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "property_id",
            "name",
            "start_date",
            "end_date",
            name="uq_student_academic_cycle_property_name_dates",
        ),
    )
    op.create_index(
        "ix_student_academic_cycles_organization_id",
        "student_academic_cycles",
        ["organization_id"],
    )
    op.create_index(
        "ix_student_academic_cycles_property_id",
        "student_academic_cycles",
        ["property_id"],
    )
    op.create_index(
        "ix_student_academic_cycles_start_date",
        "student_academic_cycles",
        ["start_date"],
    )
    op.create_index(
        "ix_student_academic_cycles_end_date",
        "student_academic_cycles",
        ["end_date"],
    )

    op.create_table(
        "student_beds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.Integer(),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bed_label", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("unit_id", "bed_label", name="uq_student_bed_unit_label"),
    )
    op.create_index("ix_student_beds_organization_id", "student_beds", ["organization_id"])
    op.create_index("ix_student_beds_property_id", "student_beds", ["property_id"])
    op.create_index("ix_student_beds_unit_id", "student_beds", ["unit_id"])

    gate = sa.table(
        "release_gates",
        sa.column("key", sa.String()),
        sa.column("stage", sa.String()),
        sa.column("description", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    now = datetime.utcnow()
    op.bulk_insert(
        gate,
        [
            {
                "key": "release.properties.student_housing",
                "stage": "HIDDEN",
                "description": "Student housing academic cycles and by-the-bed foundation",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for student-housing foundation records."
    )
