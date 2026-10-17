"""Manual trust-account interest review record: no interest allocation or posting."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from app.core.database import Base


class TrustInterestReadiness(Base):
    __tablename__ = "trust_interest_readiness"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    jurisdiction = Column(String(80), nullable=True)
    proposed_recipient = Column(String(24), nullable=False, default="UNDETERMINED")
    basis_reference = Column(String(200), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "bank_account_id", name="uq_trust_interest_org_bank"),
    )
