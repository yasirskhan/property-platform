"""Phase 4.10 by-the-bed lease references and guarantor workflow."""

from alembic import op
import sqlalchemy as sa


revision = "ae6c8d0f2b4c"
down_revision = "9d5f7b1c3e8a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("leases") as batch:
        batch.add_column(sa.Column("student_bed_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("student_academic_cycle_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_leases_student_bed_id",
            "student_beds",
            ["student_bed_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_leases_student_academic_cycle_id",
            "student_academic_cycles",
            ["student_academic_cycle_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_leases_student_bed_id", ["student_bed_id"])
        batch.create_index(
            "ix_leases_student_academic_cycle_id",
            ["student_academic_cycle_id"],
        )

    op.create_table(
        "student_guarantors",
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
            "lease_id",
            sa.Integer(),
            sa.ForeignKey("leases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("relationship_to_tenant", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("requested_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "lease_id",
            "email",
            name="uq_student_guarantor_lease_email",
        ),
    )
    op.create_index(
        "ix_student_guarantors_organization_id",
        "student_guarantors",
        ["organization_id"],
    )
    op.create_index(
        "ix_student_guarantors_property_id",
        "student_guarantors",
        ["property_id"],
    )
    op.create_index(
        "ix_student_guarantors_lease_id",
        "student_guarantors",
        ["lease_id"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for student-housing lease/guarantor records."
    )
