"""Association-approved annual budget to independently board-decided assessment increase."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from app.core.database import Base

class HOAAnnualAssessmentIncrease(Base):
    __tablename__ = "hoa_annual_assessment_increases"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    budget_id = Column(Integer, ForeignKey("hoa_annual_budgets.id"), nullable=False)
    source_charge_id = Column(Integer, ForeignKey("hoa_member_assessment_charges.id"), nullable=False)
    proposal_id = Column(Integer, ForeignKey("hoa_assessment_proposals.id"), nullable=False, unique=True)
    member_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    previous_amount = Column(Numeric(14, 2), nullable=False)
    proposed_amount = Column(Numeric(14, 2), nullable=False)
    effective_on = Column(Date, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("budget_id", "source_charge_id", name="uq_hoa_increase_budget_charge"),
        Index("ix_hoa_increase_scope", "organization_id", "association_id", "property_id", "budget_id"),
    )
