"""Platform-run migration metadata.

Phase 4.13 starts with AppFolio, but the run record is provider-labelled so
later competitor adapters can reuse the same operational history without
mixing customer-side identities into platform tooling.

No provider credentials or raw provider payloads are stored here.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class PlatformMigrationRun(Base):
    __tablename__ = "platform_migration_runs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    source_account_ref = Column(String(255), nullable=False)
    status = Column(
        String(32),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
        index=True,
    )
    last_dry_run_fingerprint = Column(String(64), nullable=True, index=True)
    last_dry_run_summary = Column(JSON, nullable=True)
    created_by_platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization = relationship("Organization")
    created_by_platform_user = relationship("PlatformUser")
    items = relationship(
        "PlatformMigrationItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    uploads = relationship(
        "PlatformMigrationUpload",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    correction_rules = relationship(
        "PlatformMigrationCorrectionRule",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class PlatformMigrationUpload(Base):
    """Metadata for a staged CSV/XLSX source file.

    Raw file bytes are intentionally not persisted. The normalized fingerprint
    binds the selected sheet, header mapping and normalized staged source data.
    """

    __tablename__ = "platform_migration_uploads"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        Integer,
        ForeignKey("platform_migration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_format = Column(String(16), nullable=False)
    file_sha256 = Column(String(64), nullable=False, index=True)
    normalized_fingerprint = Column(String(64), nullable=False, index=True)
    detected_resource = Column(String(32), nullable=False, index=True)
    sheet_name = Column(String(255), nullable=False)
    headers = Column(JSON, nullable=False)
    column_mapping = Column(JSON, nullable=False)
    validation_summary = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False, index=True)
    row_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_by_platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    run = relationship("PlatformMigrationRun", back_populates="uploads")
    organization = relationship("Organization")
    created_by_platform_user = relationship("PlatformUser")
    rows = relationship(
        "PlatformMigrationStagedRow",
        back_populates="upload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "normalized_fingerprint",
            name="uq_platform_migration_upload_fingerprint",
        ),
    )


class PlatformMigrationStagedRow(Base):
    """Normalized staging data only; never a customer business record."""

    __tablename__ = "platform_migration_staged_rows"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(
        Integer,
        ForeignKey("platform_migration_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(
        Integer,
        ForeignKey("platform_migration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    resource = Column(String(32), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    source_id = Column(String(255), nullable=True, index=True)
    disposition = Column(String(32), nullable=False, index=True)
    row_fingerprint = Column(String(64), nullable=False, index=True)
    normalized_data = Column(JSON, nullable=False)
    correction_evidence = Column(JSON, nullable=False, default=list, server_default="[]")
    warnings = Column(JSON, nullable=False)
    errors = Column(JSON, nullable=False)
    resolution_action = Column(String(32), nullable=True, index=True)
    resolution_target_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resolution_target_unit_id = Column(
        Integer,
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resolution_target_owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resolution_target_vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resolution_target_tenant_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resolution_target_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    resolved_by_platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    upload = relationship("PlatformMigrationUpload", back_populates="rows")
    run = relationship("PlatformMigrationRun", back_populates="correction_rules")
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint(
            "upload_id",
            "row_number",
            name="uq_platform_migration_staged_row_number",
        ),
    )


class PlatformMigrationCorrectionRule(Base):
    """Run-scoped exact-value correction rule for migration staging only."""

    __tablename__ = "platform_migration_correction_rules"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        Integer,
        ForeignKey("platform_migration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    resource = Column(String(32), nullable=False, index=True)
    field_name = Column(String(64), nullable=False)
    source_value = Column(String(500), nullable=False)
    corrected_value = Column(String(500), nullable=False)
    created_by_platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    run = relationship("PlatformMigrationRun")
    organization = relationship("Organization")
    created_by_platform_user = relationship("PlatformUser")

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "resource",
            "field_name",
            "source_value",
            name="uq_platform_migration_correction_rule_source",
        ),
    )


class PlatformMigrationItem(Base):
    """Durable provider source-to-target mapping for replay-safe migration commits."""

    __tablename__ = "platform_migration_items"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        Integer,
        ForeignKey("platform_migration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    resource = Column(String(32), nullable=False, index=True)
    source_id = Column(String(255), nullable=False)
    target_entity = Column(String(64), nullable=False)
    target_id = Column(Integer, nullable=False, index=True)
    source_fingerprint = Column(String(64), nullable=False, index=True)
    created_by_platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    run = relationship("PlatformMigrationRun", back_populates="items")
    organization = relationship("Organization")
    created_by_platform_user = relationship("PlatformUser")

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "resource",
            "source_id",
            name="uq_platform_migration_item_source",
        ),
    )
