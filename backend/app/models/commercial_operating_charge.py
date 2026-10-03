"""Operational Commercial CAM/NNN tenant charges posted through central GL."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from app.core.database import Base


class CommercialOperatingCharge(Base):
    __tablename__ = "commercial_operating_charges"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False, index=True)
    abstract_id = Column(Integer, ForeignKey("commercial_lease_abstracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    terms_id = Column(Integer, ForeignKey("commercial_lease_terms.id", ondelete="RESTRICT"), nullable=False, index=True)
    tenant_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind = Column(String(12), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    posting_on = Column(Date, nullable=False)
    due_on = Column(Date, nullable=False)
    cam_amount = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    tax_amount = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    insurance_amount = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    total_amount = Column(Numeric(14, 2), nullable=False)
    receivable_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)
    income_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)
    charge_id = Column(Integer, ForeignKey("charges.id", ondelete="RESTRICT"), nullable=False, unique=True)
    gl_transaction_id = Column(Integer, ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    reversal_transaction_id = Column(Integer, ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True)
    request_key = Column(String(96), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED", server_default="POSTED")
    reversal_on = Column(Date, nullable=True)
    reversal_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_commercial_operating_charge_request"),
        Index("ix_commercial_operating_charge_scope", "organization_id", "property_id", "lease_id", "status"),
    )
