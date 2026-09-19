# ============================================================
# models/property.py
# ------------------------------------------------------------
# Database tables for:
#   - Properties (buildings owned by an organization)
#   - Units (individual rentable spaces inside a property)
#   - PropertyAssignments (which manager/crew works at which property)
# ============================================================

import enum
from datetime import datetime, date

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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.user import UserRole


# ------------------------------------------------------------
# PROPERTY TYPES
# ------------------------------------------------------------
class PropertyType(str, enum.Enum):
    SINGLE_FAMILY = "single_family"
    MULTI_FAMILY = "multi_family"
    APARTMENT = "apartment"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"
    COMMERCIAL = "commercial"
    OTHER = "other"


# ------------------------------------------------------------
# PROPERTY
# ------------------------------------------------------------
class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)

    # Which organization owns this property
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # --- Basic info ---
    name = Column(String(255), nullable=False)
    property_type = Column(SqlEnum(PropertyType), nullable=False, default=PropertyType.MULTI_FAMILY)

    # --- Address ---
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    zip_code = Column(String(20), nullable=False)
    country = Column(String(100), nullable=False, default="USA")

    # --- Physical details ---
    year_built = Column(Integer, nullable=True)
    year_renovated = Column(Integer, nullable=True)
    square_feet = Column(Integer, nullable=True)
    stories = Column(Integer, nullable=True)
    parking_spaces = Column(Integer, nullable=True)
    parking_type = Column(String(50), nullable=True)  # garage, off_street, on_street, none

    # --- Financial ---
    estimated_rent = Column(Numeric(10, 2), nullable=True)
    security_deposit = Column(Numeric(10, 2), nullable=True)
    ownership_status = Column(String(50), nullable=True)

    
    # --- Policies ---
    pets_allowed = Column(Boolean, default=False)
    pet_types_allowed = Column(String(100), nullable=True)
    max_pets = Column(Integer, nullable=True)
    weight_limit_lbs = Column(Integer, nullable=True)
    breed_restrictions = Column(Text, nullable=True)
    pet_deposit = Column(Numeric(10, 2), nullable=True)
    pet_rent = Column(Numeric(10, 2), nullable=True)
    smoking_allowed = Column(Boolean, default=False)
    lease_term_months = Column(Integer, nullable=True)
    available_from = Column(Date, nullable=True)

    # --- Tenant Insurance ---
    renters_insurance_required = Column(Boolean, default=False)
    renters_insurance_min_coverage = Column(Numeric(12, 2), nullable=True)
    renters_insurance_required_at_movein = Column(Boolean, default=False)
    renters_insurance_notes = Column(Text, nullable=True)

    # --- Laundry ---
    laundry_type = Column(String(50), nullable=True)  # in_unit, shared_on_site, hookups_only, none
    shared_laundry_location = Column(String(255), nullable=True)
    shared_laundry_cost = Column(String(100), nullable=True)
    shared_laundry_notes = Column(Text, nullable=True)

    # --- Description ---
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # --- Status ---
    is_active = Column(Boolean, default=True)

    # --- Soft delete ---
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delete_reason = Column(Text, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Relationships ---
    units = relationship("Unit", back_populates="property", cascade="all, delete-orphan")
    assignments = relationship("PropertyAssignment", back_populates="property", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Property {self.name} ({self.city}, {self.state})>"


# ------------------------------------------------------------
# UNIT
# ------------------------------------------------------------
class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(
        Integer,
        ForeignKey("properties.id"),
        nullable=False,
        index=True,
    )

    # --- Unit identity ---
    unit_number = Column(String(50), nullable=False)

    # --- Layout ---
    bedrooms = Column(Integer, nullable=False, default=0)
    bathrooms = Column(Numeric(3, 1), nullable=False, default=0)
    square_feet = Column(Integer, nullable=True)

    # --- Rent & fees ---
    monthly_rent = Column(Numeric(10, 2), nullable=False, default=0.00)
    security_deposit = Column(Numeric(10, 2), nullable=True)
    pet_deposit = Column(Numeric(10, 2), nullable=True)
    pet_rent = Column(Numeric(10, 2), nullable=True)
    application_fee = Column(Numeric(10, 2), nullable=True)
    admin_fee = Column(Numeric(10, 2), nullable=True)

    # --- Availability ---
    is_available = Column(Boolean, default=True)
    available_from = Column(Date, nullable=True)
    lease_term_months = Column(Integer, nullable=True)
    is_listed = Column(Boolean, default=False)

    # --- Status ---
    is_active = Column(Boolean, default=True)

    # --- Soft delete ---
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delete_reason = Column(Text, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Relationships ---
    property = relationship("Property", back_populates="units")

    __table_args__ = (
        UniqueConstraint("property_id", "unit_number", name="uq_property_unit_number"),
    )

    def __repr__(self):
        return f"<Unit {self.unit_number} at property {self.property_id}>"


# ------------------------------------------------------------
# PROPERTY ASSIGNMENT
# ------------------------------------------------------------
class PropertyAssignment(Base):
    __tablename__ = "property_assignments"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(
        Integer,
        ForeignKey("properties.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    role = Column(SqlEnum(UserRole), nullable=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- Relationships ---
    property = relationship("Property", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("property_id", "user_id", name="uq_property_user"),
    )

    def __repr__(self):
        return f"<PropertyAssignment user={self.user_id} property={self.property_id} role={self.role.value}>"