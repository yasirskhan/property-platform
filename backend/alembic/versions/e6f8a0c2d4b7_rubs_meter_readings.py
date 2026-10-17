"""Phase 4.9 RUBs raw meter readings.

Revision ID: e6f8a0c2d4b7
Revises: d5f7a9c1e3b6
"""
from alembic import op
import sqlalchemy as sa

revision = "e6f8a0c2d4b7"
down_revision = "d5f7a9c1e3b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "utility_meter_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "utility_id",
            sa.Integer(),
            sa.ForeignKey("property_utilities.id"),
            nullable=False,
        ),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=True),
        sa.Column("meter_identifier", sa.String(length=120), nullable=False),
        sa.Column("reading_date", sa.Date(), nullable=False),
        sa.Column("reading_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("import_batch_key", sa.String(length=96), nullable=True),
        sa.Column("request_key", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "utility_id",
            "request_key",
            name="uq_utility_meter_reading_request",
        ),
    )
    op.create_index(
        "ix_utility_meter_readings_utility_id",
        "utility_meter_readings",
        ["utility_id"],
    )
    op.create_index(
        "ix_utility_meter_readings_unit_id",
        "utility_meter_readings",
        ["unit_id"],
    )
    op.create_index(
        "ix_utility_meter_readings_reading_date",
        "utility_meter_readings",
        ["reading_date"],
    )
    op.create_index(
        "ix_utility_meter_readings_import_batch_key",
        "utility_meter_readings",
        ["import_batch_key"],
    )


def downgrade():
    op.drop_table("utility_meter_readings")
