"""Vendor liability insurance records; no property premiums or GL postings."""
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class VendorInsurance(Base):
    __tablename__ = "vendor_insurances"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    vendor_id = Column(
        Integer, ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    carrier = Column(String(255), nullable=False)
    coverage_type = Column(String(100), nullable=False)
    policy_number = Column(String(100), nullable=True)
    coverage_amount = Column(Numeric(14, 2), nullable=True)
    effective_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    deleted_at = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship("Vendor")

    __table_args__ = (
        Index("ix_vendor_insurance_org_vendor_expiry", "organization_id", "vendor_id", "expiration_date"),
    )
