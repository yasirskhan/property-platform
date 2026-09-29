"""Association-specific annual operating budgets and immutable board decisions.

Figures are approved planning authorizations, never posted GL, reserve transfers,
or approval of individual member assessment increases.
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from app.core.database import Base


class HOAAnnualBudget(Base):
    __tablename__ = "hoa_annual_budgets"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    calendar_year = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    description = Column(String(300), nullable=False)
    # Snapshot is the unique source for this association budget, NOT the
    # potentially unrelated shared PropertyBudgetLine inventory.
    lines_json = Column(Text, nullable=False)
    total_income = Column(Numeric(14, 2), nullable=False)
    total_expense = Column(Numeric(14, 2), nullable=False)
    reserve_allocation = Column(Numeric(14, 2), nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"))
    decision_maker_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"))
    decision_method = Column(String(16))
    decided_on = Column(Date)
    decided_at = Column(DateTime)
    decision_note = Column(Text)
    supporting_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"))
    created_by_id = Column(Integer, ForeignKey("users.id"))
    decided_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("association_id", "property_id", "calendar_year",
                         "revision", name="uq_hoa_annual_budget_revision"),
        Index("ix_hoa_annual_budget_scope", "organization_id", "association_id",
              "property_id", "calendar_year", "is_active"),
    )
