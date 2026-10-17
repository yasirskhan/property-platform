"""Per-bank check stock and automatic numbering configuration."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class BankCheckSetup(Base):
    __tablename__ = "bank_check_setups"
    __table_args__ = (UniqueConstraint("organization_id", "bank_account_id", name="uq_bank_check_setup_org_bank"),)
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    next_check_number = Column(Integer, nullable=False, default=1, server_default="1")
    check_number_prefix = Column(String(20), nullable=True)
    check_stock_position = Column(String(10), nullable=False, default="TOP", server_default="TOP")
    memo_line_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    signature_line_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    bank_account = relationship("BankAccount")
