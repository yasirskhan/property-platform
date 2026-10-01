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
