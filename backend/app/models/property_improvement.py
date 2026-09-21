# ============================================================
# property_improvement.py
# ------------------------------------------------------------
# A renovation / upgrade on a property (kitchen remodel, roof
# replacement, etc.). Pure CRUD — no GL impact.
#
# AppFolio parity: improvements live on the property detail
# page as a list with date, description, category, contractor,
# and cost.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PropertyImprovement(Base):
    __tablename__ = "property_improvements"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    improvement_date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    cost = Column(Numeric(14, 2), nullable=True)
    contractor = Column(String(200), nullable=True)

    # Kitchen | Bath | Roof | HVAC | Flooring | Electrical |
    # Plumbing | Exterior | Other
    category = Column(String(60), nullable=True)

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    property = relationship("Property")
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return (
            f"<PropertyImprovement {self.id} property={self.property_id} "
            f"{self.improvement_date} {self.description[:30]}>"
        )