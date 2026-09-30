"""Phase 4.10 student-housing foundation stays explicit and finance-neutral."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.property import (
    Property,
    PropertyAssignment,
    StudentAcademicCycle,
    StudentBed,
    Unit,
)
from app.models.user import Organization, User, UserRole
from app.routers import student_housing as api
from app.schemas.student_housing import AcademicCycleCreate, StudentBedCreate


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(
        api,
        "resolve_customer_features",
        lambda *a, **kw: [SimpleNamespace(key=api.FEATURE_KEY, allowed=True)],
    )


def _seed(db):
    org = Organization(name="Student Housing", slug="student-housing")
    other_org = Organization(name="Student Foreign", slug="student-foreign")
    db.add_all([org, other_org])
    db.flush()

    admin = User(
        organization_id=org.id,
        role=UserRole.ADMIN,
        first_name="Student",
        last_name="Admin",
        email="student-admin@example.com",
        hashed_password="x",
        is_active=True,
    )
    manager = User(
        organization_id=org.id,
        role=UserRole.MANAGER,
        first_name="Student",
        last_name="Manager",
        email="student-manager@example.com",
        hashed_password="x",
        is_active=True,
    )
    db.add_all([admin, manager])
    db.flush()

    prop = Property(
        organization_id=org.id,
        name="Campus Property",
        address_line1="1 College Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        is_active=True,
    )
    foreign_prop = Property(
        organization_id=other_org.id,
        name="Foreign Campus",
        address_line1="2 College Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        is_active=True,
    )
    db.add_all([prop, foreign_prop])
    db.flush()
    db.add(
        PropertyAssignment(
            property_id=prop.id,
            user_id=manager.id,
            role=UserRole.MANAGER,
            is_active=True,
        )
    )

    unit = Unit(
        property_id=prop.id,
        unit_number="A-101",
        bedrooms=2,
        bathrooms=1,
        monthly_rent=Decimal("1200"),
        is_active=True,
    )
    foreign_unit = Unit(
        property_id=foreign_prop.id,
        unit_number="X-1",
        bedrooms=1,
        bathrooms=1,
        monthly_rent=Decimal("900"),
        is_active=True,
    )
    db.add_all([unit, foreign_unit])
    db.commit()
    return admin, manager, prop, foreign_prop, unit, foreign_unit


def test_academic_cycles_are_property_scoped_and_manager_read_only():
    db, engine = _db()
    try:
        admin, manager, prop, foreign_prop, _, _ = _seed(db)
        created = api.create_academic_cycle(
            prop.id,
            AcademicCycleCreate(
                name="2026-27 Academic Year",
                start_date=date(2026, 8, 20),
                end_date=date(2027, 5, 15),
            ),
            db=db,
            current_user=admin,
        )
        assert created["name"] == "2026-27 Academic Year"
        rows = api.list_academic_cycles(
            prop.id, Response(), db=db, current_user=manager
        )
        assert [row["id"] for row in rows] == [created["id"]]

        with pytest.raises(HTTPException) as exc:
            api.create_academic_cycle(
                prop.id,
                AcademicCycleCreate(
                    name="Manager Draft",
                    start_date=date(2027, 8, 20),
                    end_date=date(2028, 5, 15),
                ),
                db=db,
                current_user=manager,
            )
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            api.list_academic_cycles(
                foreign_prop.id, Response(), db=db, current_user=admin
            )
        assert exc.value.status_code == 404

        assert db.query(StudentAcademicCycle).count() == 1
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_bed_inventory_requires_active_same_property_units_and_posts_no_finance():
    db, engine = _db()
    try:
        admin, manager, prop, _, unit, foreign_unit = _seed(db)
        created = api.create_student_bed(
            prop.id,
            StudentBedCreate(unit_id=unit.id, bed_label="Bed A"),
            db=db,
            current_user=admin,
        )
        assert created["unit_id"] == unit.id
        assert created["bed_label"] == "Bed A"

        rows = api.list_student_beds(
            prop.id, Response(), db=db, current_user=manager
        )
        assert [row["id"] for row in rows] == [created["id"]]

        with pytest.raises(HTTPException) as exc:
            api.create_student_bed(
                prop.id,
                StudentBedCreate(unit_id=foreign_unit.id, bed_label="Foreign"),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            api.create_student_bed(
                prop.id,
                StudentBedCreate(unit_id=unit.id, bed_label="Bed B"),
                db=db,
                current_user=manager,
            )
        assert exc.value.status_code == 403

        assert db.query(StudentBed).count() == 1
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()
