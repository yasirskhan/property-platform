# ============================================================
# property_amenity.py
# ------------------------------------------------------------
# A named amenity attached to a property (Pool, Gym, In-Unit
# Laundry, Rooftop Deck, etc.). Pure CRUD — no GL impact.
#
# AppFolio parity fields:
#   - fee_amount             (money — optional)
#   - availability_status    (INCLUDED / EXTRA_FEE / NOT_AVAILABLE)
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# Allowed availability statuses
AVAILABILITY_STATUSES = ("INCLUDED", "EXTRA_FEE", "NOT_AVAILABLE")


class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

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

    name = Column(String(120), nullable=False)
    category = Column(String(60), nullable=True)
    notes = Column(Text, nullable=True)

    fee_amount = Column(Numeric(14, 2), nullable=True)
    availability_status = Column(String(30), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    delete_reason = Column(Text, nullable=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    property = relationship("Property")
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return f"<PropertyAmenity {self.id} property={self.property_id} {self.name}>"