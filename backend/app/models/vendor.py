"""Organization-owned vendor company distinct from optional vendor-login contact."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_name = Column(String(255), nullable=False)
    trade = Column(String(100), nullable=True, index=True)
    business_email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    contact_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    deleted_at = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    contact_user = relationship("User", foreign_keys=[contact_user_id])

    __table_args__ = (
        Index("ix_vendors_org_company", "organization_id", "company_name"),
    )


class MaintenancePreferredVendor(Base):
    """Ranked configuration for one property's maintenance trade, not dispatch."""
    __tablename__ = "maintenance_preferred_vendors"
    __table_args__ = (
        UniqueConstraint("property_id", "trade", "rank", name="uq_preferred_vendor_rank"),
        UniqueConstraint("property_id", "trade", "vendor_id", name="uq_preferred_vendor_company"),
        CheckConstraint("rank BETWEEN 1 AND 3", name="ck_preferred_vendor_rank"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    trade = Column(String(100), nullable=False)
    rank = Column(Integer, nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
