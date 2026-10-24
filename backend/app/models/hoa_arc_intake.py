"""Staff-recorded architectural interest, not a submitted or decided ARC request."""
from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from app.core.database import Base


class HOAARCIntake(Base):
    __tablename__ = "hoa_arc_intakes"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    project_title = Column(String(140), nullable=False)
    staff_noted_on = Column(Date, nullable=False)
    staff_description = Column(Text, nullable=True)
    # Deliberately no applicant, approval, denial, review deadline, fee or construction permit.
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_hoa_arc_intake_scope", "organization_id", "association_id", "property_id"),
    )
