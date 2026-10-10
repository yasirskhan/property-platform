"""Staff-recorded property tour/guest card for an existing leasing prospect."""
from datetime import date, datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base

class GuestCard(Base):
    __tablename__ = "leasing_guest_cards"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    prospect_id = Column(Integer, ForeignKey("leasing_prospects.id", ondelete="RESTRICT"), nullable=False, index=True)
    visit_on = Column(Date, nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="RESTRICT"), nullable=True)
    attended = Column(Boolean, nullable=False, default=False)
    next_step = Column(String(24), nullable=False, default="NONE")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "prospect_id", "visit_on", name="uq_guest_card_org_prospect_day"),
        Index("ix_guest_cards_org_visit", "organization_id", "visit_on"),
    )
