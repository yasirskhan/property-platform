"""Phase 4.13 typed staged Unit resolution target."""

from alembic import op
import sqlalchemy as sa


revision = "c35e9d2a7b14"
down_revision = "b24d8c1f4a62"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platform_migration_staged_rows") as batch:
        batch.add_column(
            sa.Column("resolution_target_unit_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_platform_migration_staged_rows_resolution_target_unit_id",
            "units",
            ["resolution_target_unit_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_platform_migration_staged_rows_resolution_target_unit_id",
            ["resolution_target_unit_id"],
        )


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for staged Unit resolution metadata."
    )
