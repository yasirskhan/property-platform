from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.property import Property, PropertyType
from app.models.user import Organization, User, UserRole
from app.routers.properties import (
    check_property_access,
    create_property,
    restore_property,
    visible_properties_query,
)
from app.schemas.property import PropertyCreate


TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    Property.__table__,
]


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TEST_TABLES)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org_a = Organization(name="Org A", slug="org-a")
    org_b = Organization(name="Org B", slug="org-b")
    db.add_all([org_a, org_b])
    db.flush()
    admin = User(
        email="admin-a@example.com",
        hashed_password="unused",
        first_name="Admin",
        last_name="A",
        role=UserRole.ADMIN,
        organization_id=org_a.id,
        is_active=True,
    )
    prop_a = Property(
        organization_id=org_a.id,
        name="Property A",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="1 A St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
    )
    prop_b = Property(
        organization_id=org_b.id,
        name="Property B",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="2 B St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
    )
    db.add_all([admin, prop_a, prop_b])
    db.commit()
    return org_a, org_b, admin, prop_a, prop_b


def test_customer_admin_list_is_scoped_to_own_organization() -> None:
    db, engine = _session()
    try:
        org_a, _org_b, admin, prop_a, _prop_b = _seed(db)
        rows = visible_properties_query(db, admin).all()
        assert [row.id for row in rows] == [prop_a.id]
        assert all(row.organization_id == org_a.id for row in rows)
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_cannot_access_other_org_property() -> None:
    db, engine = _session()
    try:
        _org_a, _org_b, admin, _prop_a, prop_b = _seed(db)
        with pytest.raises(HTTPException) as exc:
            check_property_access(db, admin, prop_b.id)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_cannot_create_property_for_other_org() -> None:
    db, engine = _session()
    try:
        _org_a, org_b, admin, _prop_a, _prop_b = _seed(db)
        payload = PropertyCreate(
            organization_id=org_b.id,
            name="Cross Org",
            property_type=PropertyType.MULTI_FAMILY,
            address_line1="3 X St",
            city="Cleveland",
            state="OH",
            zip_code="44113",
        )
        with pytest.raises(HTTPException) as exc:
            create_property(payload, db, admin)
        assert exc.value.status_code == 403
        assert db.query(Property).filter(Property.name == "Cross Org").count() == 0
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_cannot_restore_other_org_property() -> None:
    db, engine = _session()
    try:
        _org_a, _org_b, admin, _prop_a, prop_b = _seed(db)
        prop_b.is_active = False
        db.commit()

        with pytest.raises(HTTPException) as exc:
            restore_property(prop_b.id, db, admin)
        assert exc.value.status_code == 403
        db.refresh(prop_b)
        assert prop_b.is_active is False
    finally:
        db.close()
        engine.dispose()
