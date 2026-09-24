"""Seed the deterministic account used by browser smoke tests."""
from __future__ import annotations

import os

from app.core.auth import create_user
from app.core.database import SessionLocal
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.schemas.user import UserCreate

E2E_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
E2E_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
E2E_ORG = os.environ.get("E2E_ORG_NAME", "E2E Test Organization")
E2E_PROPERTY_ID = 900001
E2E_UNIT_ID = 900001


def seed() -> None:
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError(
            "Refusing E2E seed. Set E2E_SEED_ALLOWED=true only for a disposable test database."
        )

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == E2E_EMAIL).first()
        if existing:
            raise RuntimeError(f"E2E account already exists: {E2E_EMAIL}")

        user = create_user(
            db,
            UserCreate(
                email=E2E_EMAIL,
                password=E2E_PASSWORD,
                first_name="E2E",
                last_name="Admin",
                role=UserRole.ADMIN,
                organization_name=E2E_ORG,
            ),
        )
        organization = db.get(Organization, user.organization_id)
        if organization is None:
            raise RuntimeError("Seeded E2E user is missing its organization")
        # The core authenticated smoke represents an already-paid customer.
        organization.state = "ACTIVE"

        property_obj = Property(
            id=E2E_PROPERTY_ID,
            organization_id=user.organization_id,
            name="E2E Test Property",
            property_type=PropertyType.MULTI_FAMILY,
            address_line1="100 Test Avenue",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        unit = Unit(
            id=E2E_UNIT_ID,
            property_id=E2E_PROPERTY_ID,
            unit_number="E2E-1",
            bedrooms=2,
            bathrooms=1,
            monthly_rent=1000,
            is_available=True,
            is_active=True,
        )
        db.add_all([property_obj, unit])
        db.commit()
        print(
            f"Seeded E2E admin id={user.id} org={user.organization_id} "
            f"property={property_obj.id} unit={unit.id}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
