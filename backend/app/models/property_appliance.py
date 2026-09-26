# ============================================================
# property_appliance.py
# ------------------------------------------------------------
# A physical appliance on a property (Fridge, Washer, Dryer,
# Dishwasher, etc.). Pure CRUD — no GL impact.
#
# AppFolio parity fields:
#   - condition (NEW / GOOD / FAIR / NEEDS_REPAIR)
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


# Allowed condition values
APPLIANCE_CONDITIONS = ("NEW", "GOOD", "FAIR", "NEEDS_REPAIR")


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

    name = Column(String(120), nullable=False)
    brand = Column(String(120), nullable=True)
    model_number = Column(String(120), nullable=True)
    serial_number = Column(String(120), nullable=True)
    purchase_date = Column(Date, nullable=True)
    purchase_price = Column(Numeric(14, 2), nullable=True)
    warranty_expires = Column(Date, nullable=True)
    condition = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)

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
        return (
            f"<PropertyAppliance {self.id} property={self.property_id} "
            f"{self.name}>"
        )