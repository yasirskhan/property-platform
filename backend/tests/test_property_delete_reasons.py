from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.property import Property, PropertyType
from app.models.property_amenity import PropertyAmenity
from app.models.property_appliance import PropertyAppliance
from app.models.property_improvement import PropertyImprovement
from app.models.user import Organization, User, UserRole
from app.routers import property_amenities, property_appliances, property_improvements


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Delete Reason Org", slug="delete-reason-org")
    db.add(org)
    db.flush()
    user = User(
        email="delete-reason@example.com",
        hashed_password=hash_password("test1234"),
        first_name="Delete",
        last_name="Reason",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    prop = Property(
        organization_id=org.id,
        name="Delete Reason Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="100 Test Avenue",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add_all([user, prop])
    db.flush()
    amenity = PropertyAmenity(
        organization_id=org.id,
        property_id=prop.id,
        name="Pool",
        is_active=True,
        created_by_id=user.id,
    )
    appliance = PropertyAppliance(
        organization_id=org.id,
        property_id=prop.id,
        name="Refrigerator",
        is_active=True,
        created_by_id=user.id,
    )
    improvement = PropertyImprovement(
        organization_id=org.id,
        property_id=prop.id,
        improvement_date=date(2026, 9, 25),
        description="Kitchen refresh",
        is_active=True,
        created_by_id=user.id,
    )
    db.add_all([amenity, appliance, improvement])
    db.commit()
    return user, prop, amenity, appliance, improvement


def test_property_detail_soft_deletes_persist_reason():
    db, engine = _session()
    try:
        user, prop, amenity, appliance, improvement = _seed(db)

        property_amenities.delete_amenity(
            property_id=prop.id,
            amenity_id=amenity.id,
            reason="Pool permanently closed",
            db=db,
            current_user=user,
        )
        property_appliances.delete_appliance(
            property_id=prop.id,
            appliance_id=appliance.id,
            reason="Replaced during renovation",
            db=db,
            current_user=user,
        )
        property_improvements.delete_improvement(
            property_id=prop.id,
            improvement_id=improvement.id,
            reason="Duplicate improvement record",
            db=db,
            current_user=user,
        )

        db.refresh(amenity)
        db.refresh(appliance)
        db.refresh(improvement)
        assert amenity.is_active is False
        assert amenity.delete_reason == "Pool permanently closed"
        assert appliance.is_active is False
        assert appliance.delete_reason == "Replaced during renovation"
        assert improvement.is_active is False
        assert improvement.delete_reason == "Duplicate improvement record"
    finally:
        db.close()
        engine.dispose()
