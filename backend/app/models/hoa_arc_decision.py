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
    # For offline decisions, record both the decision maker and the officer
    # entering the record. Existing direct decisions retain the same seat.
    decision_maker_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id", ondelete="RESTRICT"), nullable=True)
    decided_on = Column(Date, nullable=True)
    record_method = Column(String(16), nullable=False, default="DIRECT", server_default="DIRECT")
    supporting_attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=True)

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
    reversal_transaction_id = Column(Integer, ForeignKey("gl_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True)
    reversal_reason = Column(Text, nullable=True)
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


class HOAARCFollowUp(Base):
    """HOA inspection or work order request; never invent a tenant or lease."""
    __tablename__ = "hoa_arc_follow_ups"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    decision_id = Column(Integer, ForeignKey("hoa_arc_decisions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    kind = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="OPEN", server_default="OPEN")
    existing_work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True)
    completion_on = Column(Date, nullable=True)
    completion_note = Column(Text, nullable=True)
    completion_attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=True)
    completion_request_key = Column(String(64), nullable=True)
    completed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_hoa_arc_follow_up_scope", "organization_id", "association_id", "property_id"),
        UniqueConstraint("organization_id", "completion_request_key", name="uq_hoa_arc_follow_up_completion_request"),
    )


class HOAARCNotification(Base):
    """Transactional outbox; delivery retries never re-execute ARC posting."""
    __tablename__ = "hoa_arc_notifications"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    decision_id = Column(Integer, ForeignKey("hoa_arc_decisions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING", server_default="PENDING")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_hoa_arc_notification_scope", "organization_id", "association_id", "property_id"),
    )
