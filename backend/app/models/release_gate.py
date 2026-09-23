"""Release-gate storage for pages and independently releasable capabilities."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReleaseStage(str, enum.Enum):
    HIDDEN = "HIDDEN"
    BETA = "BETA"
    ROLLOUT = "ROLLOUT"
    ALL_ORGS = "ALL_ORGS"


class ReleaseGate(Base):
    __tablename__ = "release_gates"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(200), nullable=False, unique=True, index=True)
    stage = Column(
        SqlEnum(
            ReleaseStage,
            name="release_stage",
            native_enum=False,
            length=20,
            values_callable=lambda stages: [stage.value for stage in stages],
        ),
        nullable=False,
        default=ReleaseStage.HIDDEN,
        server_default=ReleaseStage.HIDDEN.value,
        index=True,
    )
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organizations = relationship(
        "ReleaseGateOrganization",
        back_populates="gate",
        cascade="all, delete-orphan",
    )


class ReleaseGateOrganization(Base):
    __tablename__ = "release_gate_organizations"
    __table_args__ = (
        UniqueConstraint(
            "release_gate_id",
            "organization_id",
            name="uq_release_gate_organization",
        ),
    )

    id = Column(Integer, primary_key=True)
    release_gate_id = Column(
        Integer,
        ForeignKey("release_gates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    gate = relationship("ReleaseGate", back_populates="organizations")
    organization = relationship("Organization")
