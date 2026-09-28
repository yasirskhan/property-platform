"""Final ARC board decisions and member-specific fees; one decision per application.

These records are immutable after creation. A proposed board seat without an
authenticated matching login cannot finalize an application.
"""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from app.core.database import Base


class HOAARCDecision(Base):
    __tablename__ = "hoa_arc_decisions"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("hoa_arc_applications.id", ondelete="CASCADE"), nullable=False, unique=True)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id", ondelete="RESTRICT"), nullable=False)
    board_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision = Column(String(16), nullable=False)
    decision_note = Column(Text, nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True)
    notification_status = Column(String(32), nullable=False, default="NO_VERIFIED_RECIPIENT", server_default="NO_VERIFIED_RECIPIENT")
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_hoa_arc_decision_scope", "organization_id", "association_id", "property_id"),
    )


class HOAARCMemberCharge(Base):
    """Association member receivable; not an unrelated tenant Charge."""

    __tablename__ = "hoa_arc_member_charges"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("hoa_arc_applications.id", ondelete="CASCADE"), nullable=False, unique=True)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False)
    member_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    gl_transaction_id = Column(Integer, ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    income_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)
    receivable_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    due_on = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="OPEN", server_default="OPEN")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_hoa_arc_member_charge_scope", "organization_id", "association_id", "property_id", "member_user_id"),
    )
