"""A staff-planned HOA reserve GL movement. Never posts or moves funds."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from app.core.database import Base


class HOAReserveMovementDraft(Base):
    __tablename__ = "hoa_reserve_movement_drafts"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    reserve_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    counterparty_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    direction = Column(String(16), nullable=False)
    planned_on = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    memo = Column(String(240), nullable=False)
    idempotency_key = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT", server_default="DRAFT")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancelled_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_hoa_reserve_plan_idempotency"),
        Index("ix_hoa_reserve_plan_scope", "organization_id", "association_id", "property_id"),
    )
