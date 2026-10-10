"""Phase 4.13 CSV/XLSX ingestion and staging foundation."""

from alembic import op
import sqlalchemy as sa


revision = "f13c7a9e2b40"
down_revision = "e57c9b1d3f20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_migration_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("platform_migration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=16), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("normalized_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("detected_resource", sa.String(length=32), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("column_mapping", sa.JSON(), nullable=False),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_platform_user_id", sa.Integer(), sa.ForeignKey("platform_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", "normalized_fingerprint", name="uq_platform_migration_upload_fingerprint"),
    )
    for name, columns in (
        ("ix_platform_migration_uploads_run_id", ["run_id"]),
        ("ix_platform_migration_uploads_organization_id", ["organization_id"]),
        ("ix_platform_migration_uploads_provider", ["provider"]),
        ("ix_platform_migration_uploads_file_sha256", ["file_sha256"]),
        ("ix_platform_migration_uploads_normalized_fingerprint", ["normalized_fingerprint"]),
        ("ix_platform_migration_uploads_detected_resource", ["detected_resource"]),
        ("ix_platform_migration_uploads_status", ["status"]),
        ("ix_platform_migration_uploads_created_by_platform_user_id", ["created_by_platform_user_id"]),
    ):
        op.create_index(name, "platform_migration_uploads", columns)

    op.create_table(
        "platform_migration_staged_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_id", sa.Integer(), sa.ForeignKey("platform_migration_uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("platform_migration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=32), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("row_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("upload_id", "row_number", name="uq_platform_migration_staged_row_number"),
    )
    for name, columns in (
        ("ix_platform_migration_staged_rows_upload_id", ["upload_id"]),
        ("ix_platform_migration_staged_rows_run_id", ["run_id"]),
        ("ix_platform_migration_staged_rows_organization_id", ["organization_id"]),
        ("ix_platform_migration_staged_rows_provider", ["provider"]),
        ("ix_platform_migration_staged_rows_resource", ["resource"]),
        ("ix_platform_migration_staged_rows_source_id", ["source_id"]),
        ("ix_platform_migration_staged_rows_disposition", ["disposition"]),
        ("ix_platform_migration_staged_rows_row_fingerprint", ["row_fingerprint"]),
    ):
        op.create_index(name, "platform_migration_staged_rows", columns)


def downgrade():
    raise RuntimeError(
        "Downgrade is intentionally disabled for platform migration staging records."
    )
