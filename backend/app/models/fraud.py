"""Fraud/abuse review queue and durable risk-signal storage."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FraudCaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    DISMISSED = "DISMISSED"


class FraudRiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudCase(Base):
    __tablename__ = "fraud_cases"
    __table_args__ = (
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_fraud_cases_risk_score",
        ),
        UniqueConstraint(
            "provider",
            "provider_case_id",
            name="uq_fraud_cases_provider_case",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    checkout_session_id = Column(
        Integer,
        ForeignKey("billing_checkout_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider = Column(
        String(32),
        nullable=False,
        default="internal",
        server_default="internal",
        index=True,
    )
    provider_case_id = Column(String(255), nullable=True)
    status = Column(
        SqlEnum(
            FraudCaseStatus,
            name="fraud_case_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=FraudCaseStatus.OPEN,
        server_default=FraudCaseStatus.OPEN.value,
        index=True,
    )
    risk_level = Column(
        SqlEnum(
            FraudRiskLevel,
            name="fraud_risk_level",
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=FraudRiskLevel.LOW,
        server_default=FraudRiskLevel.LOW.value,
        index=True,
    )
    risk_score = Column(Integer, nullable=True)
    reason = Column(String(500), nullable=False)
    details = Column(JSON, nullable=False, default=dict, server_default="{}")
    reviewed_by_platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    signals = relationship(
        "FraudSignal",
        back_populates="fraud_case",
        cascade="all, delete-orphan",
        order_by="FraudSignal.id",
    )


class FraudSignal(Base):
    __tablename__ = "fraud_signals"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "provider_event_id",
            name="uq_fraud_signals_source_event",
        ),
    )

    id = Column(Integer, primary_key=True)
    fraud_case_id = Column(
        Integer,
        ForeignKey("fraud_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source = Column(String(32), nullable=False, index=True)
    signal_type = Column(String(120), nullable=False, index=True)
    severity = Column(
        SqlEnum(
            FraudRiskLevel,
            name="fraud_signal_severity",
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        index=True,
    )
    provider_event_id = Column(String(255), nullable=True)
    signal_value = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    fraud_case = relationship("FraudCase", back_populates="signals")
