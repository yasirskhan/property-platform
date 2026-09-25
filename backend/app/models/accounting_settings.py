"""Organization-wide accounting presentation and posting defaults."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class AccountingSettings(Base):
    __tablename__ = "accounting_settings"

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    gpr_rent_gl_account_id = Column(
        Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True
    )
    gpr_market_gl_account_id = Column(
        Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True
    )
    gpr_loss_gain_gl_account_id = Column(
        Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True
    )
    receipt_cash_gl_account_id = Column(
        Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True
    )
    report_export_format = Column(
        String(10), nullable=False, default="CSV", server_default="CSV"
    )
    fiscal_year_start_month = Column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization = relationship("Organization")
    gpr_rent_gl_account = relationship(
        "GLAccount", foreign_keys=[gpr_rent_gl_account_id]
    )
    gpr_market_gl_account = relationship(
        "GLAccount", foreign_keys=[gpr_market_gl_account_id]
    )
    gpr_loss_gain_gl_account = relationship(
        "GLAccount", foreign_keys=[gpr_loss_gain_gl_account_id]
    )
    receipt_cash_gl_account = relationship(
        "GLAccount", foreign_keys=[receipt_cash_gl_account_id]
    )
