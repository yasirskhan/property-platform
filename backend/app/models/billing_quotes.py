"""Billing quote models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_quotes_subtotal"),
        CheckConstraint("discount_cents >= 0", name="ck_quotes_discount"),
        CheckConstraint("total_cents >= 0", name="ck_quotes_total"),
        CheckConstraint(
            "status IN ('DRAFT','SENT','ACCEPTED','EXPIRED','CANCELLED')",
            name="ck_quotes_status",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(24), nullable=False, default="DRAFT", server_default="DRAFT", index=True)
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    subtotal_cents = Column(Integer, nullable=False, default=0, server_default="0")
    discount_cents = Column(Integer, nullable=False, default=0, server_default="0")
    total_cents = Column(Integer, nullable=False, default=0, server_default="0")
    valid_until = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    line_items = relationship(
        "QuoteLineItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteLineItem.id",
    )


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_quote_line_items_quantity"),
        CheckConstraint("unit_price_cents >= 0", name="ck_quote_line_items_unit_price"),
        CheckConstraint("line_total_cents >= 0", name="ck_quote_line_items_total"),
        CheckConstraint(
            "NOT (module_id IS NOT NULL AND add_on_id IS NOT NULL)",
            name="ck_quote_line_items_single_catalog_ref",
        ),
    )

    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = Column(Integer, ForeignKey("modules.id", ondelete="RESTRICT"), nullable=True)
    add_on_id = Column(Integer, ForeignKey("add_ons.id", ondelete="RESTRICT"), nullable=True)
    description = Column(String(500), nullable=False)
    quantity = Column(Integer, nullable=False, default=1, server_default="1")
    unit_price_cents = Column(Integer, nullable=False)
    line_total_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    quote = relationship("Quote", back_populates="line_items")
    module = relationship("Module")
    add_on = relationship("AddOn")
