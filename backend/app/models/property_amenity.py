# ============================================================
# property_amenity.py
# ------------------------------------------------------------
# A named amenity attached to a property (Pool, Gym, In-Unit
# Laundry, Rooftop Deck, etc.). Pure CRUD — no GL impact.
#
# AppFolio parity: amenities live on the property detail page
# as a simple list with optional category + notes.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


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

    # Required: "Pool", "Gym", "In-Unit Laundry", "Rooftop Deck"
    name = Column(String(120), nullable=False)

    # Optional free-text category: "Building", "Unit", "Outdoor",
    # "Community", "Other"
    category = Column(String(60), nullable=True)

    # Optional free-text notes
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
        return f"<PropertyAmenity {self.id} property={self.property_id} {self.name}>"