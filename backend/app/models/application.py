# ============================================================
# models/application.py
# ------------------------------------------------------------
# Rental applications. Permanent history.
# Applicants sign up, fill out the form, pay the fee,
# get screened, get approved/rejected.
# ============================================================

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
    Boolean,
    Numeric,
    Text,
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Import for relationship resolution
from app.models.user import User  # noqa: F401


class ApplicationStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    SCREENING = "screening"
    SCREENED = "screened"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class LeaseApplication(Base):
    __tablename__ = "lease_applications"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True, index=True)

    # The signed-up applicant account
    applicant_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Who submitted this application
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    status = Column(
        SqlEnum(ApplicationStatus),
        nullable=False,
        default=ApplicationStatus.DRAFT,
    )

    # Applicant details (JSON strings)
    applicant_names = Column(Text, nullable=True)   # JSON
    occupant_names = Column(Text, nullable=True)    # JSON
    applicant_ssn = Column(String(11), nullable=True)
    applicant_phone = Column(String(50), nullable=True)
    applicant_email = Column(String(255), nullable=True)
    applicant_dob = Column(Date, nullable=True)

    # Lease preferences
    move_in_date = Column(Date, nullable=True)
    lease_term_months = Column(Integer, nullable=True)
    pet_details = Column(Text, nullable=True)       # JSON

    # Fee
    fee_amount = Column(Numeric(10, 2), nullable=True)
    fee_waived = Column(Boolean, default=False)

    # Screening
    screening_provider = Column(String(50), nullable=True)
    screening_result = Column(Text, nullable=True)  # JSON
    screening_recommendation = Column(String(50), nullable=True)  # approve / conditional / deny

    # Review
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LeaseApplication #{self.id} status={self.status.value}>"


# ------------------------------------------------------------
# Application payments
# ------------------------------------------------------------
class ApplicationPayment(Base):
    __tablename__ = "application_payments"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(Integer, ForeignKey("lease_applications.id"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    applicant_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Denormalized name for reporting
    applicant_name = Column(String(255), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending / paid / refunded / failed
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ApplicationPayment app={self.application_id} ${self.amount} {self.status}>"