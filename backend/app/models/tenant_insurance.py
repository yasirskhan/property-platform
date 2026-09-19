# ============================================================
# models/tenant_insurance.py
# ------------------------------------------------------------
# Tenant rental insurance records.
# Uploaded by tenant OR entered by manager from a hard copy.
# Verified by owner/manager/admin. Never touches property
# expenses — it's the tenant's own cost.
# ============================================================

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
    Numeric,
    Text,
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Import for relationship resolution
from app.models.user import User  # noqa: F401


class TenantInsuranceStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExtractionStatus(str, enum.Enum):
    NOT_ATTEMPTED = "not_attempted"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFIED = "verified"


class TenantInsurance(Base):
    __tablename__ = "tenant_insurance"

    id = Column(Integer, primary_key=True, index=True)

    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)

    provider = Column(String(255), nullable=True)
    policy_number = Column(String(100), nullable=True)
    coverage_amount = Column(Numeric(12, 2), nullable=True)
    effective_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)

    document_url = Column(String(500), nullable=True)

    status = Column(
        SqlEnum(TenantInsuranceStatus),
        nullable=False,
        default=TenantInsuranceStatus.PENDING,
    )

    # OCR extraction tracking
    extraction_status = Column(
        SqlEnum(ExtractionStatus),
        nullable=False,
        default=ExtractionStatus.NOT_ATTEMPTED,
    )
    extracted_data = Column(Text, nullable=True)  # JSON

    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(500), nullable=True)

    notes = Column(Text, nullable=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TenantInsurance lease={self.lease_id} status={self.status.value}>"