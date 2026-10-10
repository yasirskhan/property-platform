"""Phase 4.10 student-housing scope, bed leases and guarantor workflow."""
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
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import (
    Property,
    PropertyAssignment,
    StudentAcademicCycle,
    StudentBed,
    StudentGuarantor,
    Unit,
)
from app.models.user import Organization, User, UserRole
from app.routers import leases as lease_api
from app.routers import student_housing as api
from app.schemas.student_housing import (
    AcademicCycleCreate,
    StudentBedCreate,
    StudentBedLeaseCreate,
    StudentGuarantorCreate,
)


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
    monkeypatch.setattr(lease_api, "_check_property_access", lambda *a, **kw: None)


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
    tenant_one = User(
        organization_id=org.id,
        role=UserRole.TENANT,
        first_name="Tenant",
        last_name="One",
        email="student-tenant-one@example.com",
        hashed_password="x",
        is_active=True,
    )
    tenant_two = User(
        organization_id=org.id,
        role=UserRole.TENANT,
        first_name="Tenant",
        last_name="Two",
        email="student-tenant-two@example.com",
        hashed_password="x",
        is_active=True,
    )
    db.add_all([admin, manager, tenant_one, tenant_two])
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
    second_unit = Unit(
        property_id=prop.id,
        unit_number="A-102",
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
    db.add_all([unit, second_unit, foreign_unit])
    db.commit()
    return (
        admin,
        manager,
        tenant_one,
        tenant_two,
        prop,
        foreign_prop,
        unit,
        second_unit,
        foreign_unit,
    )


def _cycle(db, admin, prop):
    return api.create_academic_cycle(
        prop.id,
        AcademicCycleCreate(
            name="2026-27 Academic Year",
            start_date=date(2026, 8, 20),
            end_date=date(2027, 5, 15),
        ),
        db=db,
        current_user=admin,
    )


def test_academic_cycles_are_property_scoped_and_manager_read_only():
    db, engine = _db()
    try:
        admin, manager, _, _, prop, foreign_prop, _, _, _ = _seed(db)
        created = _cycle(db, admin, prop)
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
        admin, manager, _, _, prop, _, unit, _, foreign_unit = _seed(db)
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


def test_two_beds_share_one_unit_and_use_standard_lease_lifecycle():
    db, engine = _db()
    try:
        (
            admin,
            _manager,
            tenant_one,
            tenant_two,
            prop,
            _foreign_prop,
            unit,
            second_unit,
            _foreign_unit,
        ) = _seed(db)
        cycle = _cycle(db, admin, prop)
        bed_a = api.create_student_bed(
            prop.id,
            StudentBedCreate(unit_id=unit.id, bed_label="Bed A"),
            db=db,
            current_user=admin,
        )
        bed_b = api.create_student_bed(
            prop.id,
            StudentBedCreate(unit_id=unit.id, bed_label="Bed B"),
            db=db,
            current_user=admin,
        )

        first = api.create_student_bed_lease(
            prop.id,
            StudentBedLeaseCreate(
                bed_id=bed_a["id"],
                tenant_id=tenant_one.id,
                academic_cycle_id=cycle["id"],
                start_date=date(2026, 8, 20),
                end_date=date(2027, 5, 15),
                monthly_rent=Decimal("650.00"),
                security_deposit=Decimal("300.00"),
                due_day=1,
            ),
            db=db,
            current_user=admin,
        )
        second = api.create_student_bed_lease(
            prop.id,
            StudentBedLeaseCreate(
                bed_id=bed_b["id"],
                tenant_id=tenant_two.id,
                academic_cycle_id=cycle["id"],
                start_date=date(2026, 8, 20),
                end_date=date(2027, 5, 15),
                monthly_rent=Decimal("675.00"),
                security_deposit=Decimal("300.00"),
                due_day=1,
            ),
            db=db,
            current_user=admin,
        )
        assert first["unit_id"] == second["unit_id"] == unit.id
        assert first["bed_id"] != second["bed_id"]
        assert db.query(Lease).count() == 2

        with pytest.raises(HTTPException) as exc:
            api.create_student_bed_lease(
                prop.id,
                StudentBedLeaseCreate(
                    bed_id=bed_a["id"],
                    tenant_id=tenant_two.id,
                    academic_cycle_id=cycle["id"],
                    start_date=date(2026, 8, 20),
                    end_date=date(2027, 5, 15),
                    monthly_rent=Decimal("700.00"),
                    due_day=1,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        whole_unit = Lease(
            unit_id=second_unit.id,
            tenant_id=tenant_one.id,
            start_date=date(2026, 8, 20),
            end_date=date(2027, 5, 15),
            monthly_rent=Decimal("1200.00"),
            security_deposit=Decimal("0.00"),
            due_day=1,
            status=LeaseStatus.DRAFT,
        )
        db.add(whole_unit)
        db.commit()
        second_bed = api.create_student_bed(
            prop.id,
            StudentBedCreate(unit_id=second_unit.id, bed_label="Bed A"),
            db=db,
            current_user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            api.create_student_bed_lease(
                prop.id,
                StudentBedLeaseCreate(
                    bed_id=second_bed["id"],
                    tenant_id=tenant_two.id,
                    academic_cycle_id=cycle["id"],
                    start_date=date(2026, 8, 20),
                    end_date=date(2027, 5, 15),
                    monthly_rent=Decimal("600.00"),
                    due_day=1,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        lease_api.send_lease(first["id"], db=db, current_user=admin)
        lease_api.sign_lease(first["id"], db=db, current_user=tenant_one)
        lease_api.activate_lease(first["id"], db=db, current_user=admin)

        lease_api.send_lease(second["id"], db=db, current_user=admin)
        lease_api.sign_lease(second["id"], db=db, current_user=tenant_two)
        lease_api.activate_lease(second["id"], db=db, current_user=admin)

        assert db.get(Lease, first["id"]).status == LeaseStatus.ACTIVE
        assert db.get(Lease, second["id"]).status == LeaseStatus.ACTIVE
        assert (
            db.query(RentInvoice).filter(RentInvoice.lease_id == first["id"]).count()
            > 0
        )
        assert (
            db.query(RentInvoice).filter(RentInvoice.lease_id == second["id"]).count()
            > 0
        )

        with pytest.raises(HTTPException) as exc:
            api.deactivate_student_bed(
                prop.id, bed_a["id"], db=db, current_user=admin
            )
        assert exc.value.status_code == 409
        with pytest.raises(HTTPException) as exc:
            api.deactivate_academic_cycle(
                prop.id, cycle["id"], db=db, current_user=admin
            )
        assert exc.value.status_code == 409

        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_guarantor_workflow_is_scoped_explicit_and_non_posting():
    db, engine = _db()
    try:
        admin, manager, tenant_one, _, prop, _, unit, _, _ = _seed(db)
        cycle = _cycle(db, admin, prop)
        bed = api.create_student_bed(
            prop.id,
            StudentBedCreate(unit_id=unit.id, bed_label="Bed A"),
            db=db,
            current_user=admin,
        )
        lease = api.create_student_bed_lease(
            prop.id,
            StudentBedLeaseCreate(
                bed_id=bed["id"],
                tenant_id=tenant_one.id,
                academic_cycle_id=cycle["id"],
                start_date=date(2026, 8, 20),
                end_date=date(2027, 5, 15),
                monthly_rent=Decimal("650.00"),
                due_day=1,
            ),
            db=db,
            current_user=admin,
        )

        guarantor = api.create_student_guarantor(
            prop.id,
            lease["id"],
            StudentGuarantorCreate(
                full_name="Parent One",
                email="parent.one@example.com",
                phone="216-555-0101",
                relationship_to_tenant="Parent",
            ),
            db=db,
            current_user=admin,
        )
        assert guarantor["status"] == api.GUARANTOR_DRAFT

        requested = api.mark_guarantor_requested(
            prop.id, guarantor["id"], db=db, current_user=admin
        )
        assert requested["status"] == api.GUARANTOR_REQUESTED
        assert requested["requested_at"] is not None

        received = api.record_guarantor_document_received(
            prop.id, guarantor["id"], db=db, current_user=admin
        )
        assert received["status"] == api.GUARANTOR_RECEIVED
        assert received["received_at"] is not None

        manager_rows = api.list_student_guarantors(
            prop.id, Response(), db=db, current_user=manager
        )
        assert [row["id"] for row in manager_rows] == [guarantor["id"]]

        with pytest.raises(HTTPException) as exc:
            api.create_student_guarantor(
                prop.id,
                lease["id"],
                StudentGuarantorCreate(
                    full_name="Duplicate",
                    email="PARENT.ONE@example.com",
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        with pytest.raises(HTTPException) as exc:
            api.create_student_guarantor(
                prop.id,
                lease["id"],
                StudentGuarantorCreate(
                    full_name="Manager Attempt",
                    email="manager-guarantor@example.com",
                ),
                db=db,
                current_user=manager,
            )
        assert exc.value.status_code == 403

        assert db.query(StudentGuarantor).count() == 1
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()
