# ============================================================
# property_appliance.py
# ------------------------------------------------------------
# A physical appliance on a property (Fridge, Washer, Dryer,
# Dishwasher, etc.). Pure CRUD — no GL impact.
#
# AppFolio parity: appliances live on the property detail page
# as a list with brand / model / serial / purchase info.
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


class PropertyAppliance(Base):
    __tablename__ = "property_appliances"

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

    # "Fridge", "Washer", "Dryer", "Dishwasher", etc.
    name = Column(String(120), nullable=False)

    brand = Column(String(120), nullable=True)
    model_number = Column(String(120), nullable=True)
    serial_number = Column(String(120), nullable=True)

    purchase_date = Column(Date, nullable=True)
    purchase_price = Column(Numeric(14, 2), nullable=True)
    warranty_expires = Column(Date, nullable=True)

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
            f"<PropertyAppliance {self.id} property={self.property_id} "
            f"{self.name}>"
        )