"""Explicit monthly property budget by org, property, GL account and calendar year."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class PropertyBudgetLine(Base):
    __tablename__ = "property_budget_lines"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    calendar_year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    property = relationship("Property")
    account = relationship("GLAccount")

    __table_args__ = (
        UniqueConstraint("organization_id", "property_id", "gl_account_id", "calendar_year", "month",
                         name="uq_property_budget_period_account"),
    )
