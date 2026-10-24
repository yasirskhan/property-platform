"""Phase 4.12 short-term-rental channel references stay scoped and non-integrated."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.short_term_rental import ShortTermRentalChannel, ShortTermRentalNightlyPrice, ShortTermRentalTurnover
from app.models.unit_inspection import UnitInspectionRecord
from app.models.work_order import WorkOrder, WorkOrderCategory, WorkOrderPriority, WorkOrderStatus
from app.models.user import Organization, User, UserRole
from app.routers import short_term_rentals as api
from app.schemas.short_term_rental import ShortTermRentalChannelIn, ShortTermRentalNightlyPriceIn, ShortTermRentalTurnoverIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="STR One", slug="str-one")
    foreign_org = Organization(name="STR Two", slug="str-two")
    db.add_all([org, foreign_org]); db.flush()

    users = []
    for organization, role, name in (
        (org, UserRole.ADMIN, "admin"),
        (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"),
        (org, UserRole.TENANT, "tenant"),
        (foreign_org, UserRole.ADMIN, "foreign"),
    ):
        user = User(
            organization_id=organization.id,
            role=role,
            email=f"str-{name}@example.com",
            first_name=name,
            last_name="Rental",
            hashed_password="x",
            is_active=True,
        )
        db.add(user); users.append(user)
    db.flush()

    props = []
    for organization, name in (
        (org, "Assigned"),
        (org, "Unassigned"),
        (foreign_org, "Foreign"),
    ):
        prop = Property(
            organization_id=organization.id,
            name=name,
            address_line1="12 Main",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            is_active=True,
        )
        db.add(prop); props.append(prop)
    db.flush()

    db.add(PropertyAssignment(
        property_id=props[0].id,
        user_id=users[2].id,
        role=UserRole.MANAGER,
        is_active=True,
    ))
    db.commit()
    return users, props


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=api.FEATURE_KEY, allowed=True),
    ])


def _payload(**overrides):
    data = {
        "provider": "AIRBNB",
        "label": "Main Airbnb listing",
        "external_listing_id": "AIR-123",
        "public_listing_url": "https://example.com/listing/123",
        "notes": "Staff-entered listing reference only.",
    }
    data.update(overrides)
    return ShortTermRentalChannelIn(**data)


def test_channel_reference_lifecycle_scoped_audited_and_finance_neutral():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        created = api.create_channel(assigned.id, _payload(), db=db, current_user=admin)
        assert created.provider == "AIRBNB"
        assert created.external_listing_id == "AIR-123"

        response = Response()
        listed = api.list_channels(assigned.id, response, db=db, current_user=manager)
        assert [row.id for row in listed] == [created.id]
        assert response.headers["cache-control"] == "no-store"

        for actor, prop in ((manager, unassigned), (manager, other), (foreign, assigned)):
            with pytest.raises(HTTPException) as exc:
                api.list_channels(prop.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404

        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_channel(
                    assigned.id,
                    _payload(label=f"No write {actor.role.value}"),
                    db=db,
                    current_user=actor,
                )
            assert exc.value.status_code == 403

        updated = api.update_channel(
            assigned.id,
            created.id,
            _payload(provider="VRBO", label="Main Vrbo listing", external_listing_id="VRBO-9"),
            db=db,
            current_user=owner,
        )
        assert updated.provider == "VRBO"

        api.archive_channel(assigned.id, created.id, db=db, current_user=admin)
        assert api.list_channels(assigned.id, Response(), db=db, current_user=admin) == []

        assert db.query(ShortTermRentalChannel).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "short_term_rental_channel").count() == 3
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0

        columns = set(ShortTermRentalChannel.__table__.columns.keys())
        for prohibited in (
            "access_token", "refresh_token", "api_key", "password",
            "reservation_id", "booking_id", "payout_amount", "nightly_rate",
        ):
            assert prohibited not in columns
    finally:
        db.close(); engine.dispose()


def test_channel_duplicate_validation_and_feature_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, _owner, _manager, _tenant, _foreign), (assigned, _unassigned, _other) = _seed(db)
        api.create_channel(assigned.id, _payload(), db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.create_channel(assigned.id, _payload(), db=db, current_user=admin)
        assert exc.value.status_code == 409

        # Same label may be recorded separately for another provider.
        vrbo = api.create_channel(
            assigned.id,
            _payload(provider="VRBO", external_listing_id="VRBO-123"),
            db=db,
            current_user=admin,
        )
        assert vrbo.provider == "VRBO"

        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=api.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_channels(assigned.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_channel_schema_is_reference_only():
    payload = _payload(
        provider="VRBO",
        label="  Lake house  ",
        external_listing_id="  9988  ",
        public_listing_url="  https://example.com/vrbo/9988  ",
    )
    assert payload.label == "Lake house"
    assert payload.external_listing_id == "9988"
    assert payload.public_listing_url == "https://example.com/vrbo/9988"

    with pytest.raises(ValueError):
        ShortTermRentalChannelIn(provider="BOOKING_DOT_COM", label="Unsupported")



def _unit(db, property_id: int, number: str = "STR-101"):
    row = Unit(
        property_id=property_id,
        unit_number=number,
        bedrooms=1,
        bathrooms=1,
        monthly_rent=Decimal("1000.00"),
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _price_payload(unit_id: int, **overrides):
    data = {
        "unit_id": unit_id,
        "night_date": date(2026, 10, 15),
        "nightly_rate": Decimal("175.00"),
        "minimum_stay_nights": 2,
        "notes": "Staff-entered nightly price only.",
    }
    data.update(overrides)
    return ShortTermRentalNightlyPriceIn(**data)


def test_nightly_price_lifecycle_scoped_audited_and_finance_neutral():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        unit = _unit(db, assigned.id)
        foreign_unit = _unit(db, other.id, "FOREIGN-1")

        created = api.create_nightly_price(
            assigned.id,
            _price_payload(unit.id),
            db=db,
            current_user=admin,
        )
        assert created.unit_id == unit.id
        assert created.nightly_rate == Decimal("175.00")
        assert created.minimum_stay_nights == 2

        response = Response()
        listed = api.list_nightly_prices(
            assigned.id, response, db=db, current_user=manager
        )
        assert [row.id for row in listed] == [created.id]
        assert response.headers["cache-control"] == "no-store"

        with pytest.raises(HTTPException) as exc:
            api.create_nightly_price(
                assigned.id,
                _price_payload(foreign_unit.id, night_date=date(2026, 10, 16)),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404

        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_nightly_price(
                    assigned.id,
                    _price_payload(unit.id, night_date=date(2026, 10, 17)),
                    db=db,
                    current_user=actor,
                )
            assert exc.value.status_code == 403

        updated = api.update_nightly_price(
            assigned.id,
            created.id,
            _price_payload(
                unit.id,
                nightly_rate=Decimal("225.00"),
                minimum_stay_nights=3,
            ),
            db=db,
            current_user=owner,
        )
        assert updated.nightly_rate == Decimal("225.00")
        assert updated.minimum_stay_nights == 3

        api.archive_nightly_price(
            assigned.id, created.id, db=db, current_user=admin
        )
        assert api.list_nightly_prices(
            assigned.id, Response(), db=db, current_user=admin
        ) == []

        assert db.query(ShortTermRentalNightlyPrice).count() == 1
        assert (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "short_term_rental_nightly_price")
            .count()
            == 3
        )
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_nightly_price_duplicate_validation_and_feature_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, _owner, _manager, _tenant, _foreign), (assigned, _unassigned, _other) = _seed(db)
        unit = _unit(db, assigned.id)
        api.create_nightly_price(
            assigned.id, _price_payload(unit.id), db=db, current_user=admin
        )
        with pytest.raises(HTTPException) as exc:
            api.create_nightly_price(
                assigned.id, _price_payload(unit.id), db=db, current_user=admin
            )
        assert exc.value.status_code == 409

        with pytest.raises(ValueError):
            _price_payload(unit.id, nightly_rate=Decimal("-1.00"))
        with pytest.raises(ValueError):
            _price_payload(unit.id, minimum_stay_nights=0)

        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=api.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_nightly_prices(
                assigned.id, Response(), db=db, current_user=admin
            )
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def _turnover_payload(unit_id: int, **overrides):
    start = datetime(2026, 10, 20, 11, 0)
    data = {
        "unit_id": unit_id,
        "scheduled_start": start,
        "scheduled_end": start + timedelta(hours=4),
        "status": "SCHEDULED",
        "notes": "Staff-recorded turnover schedule only.",
    }
    data.update(overrides)
    return ShortTermRentalTurnoverIn(**data)


def _linked_operations(db, *, prop, unit, actor):
    work_order = WorkOrder(
        unit_id=unit.id,
        property_id=prop.id,
        tenant_id=actor.id,
        title="Turnover cleaning",
        description="Existing maintenance work order reference.",
        category=WorkOrderCategory.CLEANING,
        priority=WorkOrderPriority.MEDIUM,
        status=WorkOrderStatus.SUBMITTED,
    )
    inspection = UnitInspectionRecord(
        organization_id=prop.organization_id,
        property_id=prop.id,
        unit_id=unit.id,
        inspection_date=date(2026, 10, 20),
        recorded_condition="SATISFACTORY",
        findings="Existing explicit inspection fact.",
        recorded_by_id=actor.id,
    )
    db.add_all([work_order, inspection])
    db.commit()
    return work_order, inspection


def test_turnover_schedule_scoped_links_existing_operations_without_mutating_them():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        unit = _unit(db, assigned.id, "TURN-101")
        foreign_unit = _unit(db, other.id, "TURN-FOREIGN")
        work_order, inspection = _linked_operations(db, prop=assigned, unit=unit, actor=admin)
        foreign_work_order, foreign_inspection = _linked_operations(
            db, prop=other, unit=foreign_unit, actor=foreign
        )
        original_work_order_status = work_order.status
        original_inspection_findings = inspection.findings

        created = api.create_turnover(
            assigned.id,
            _turnover_payload(
                unit.id,
                cleaning_work_order_id=work_order.id,
                inspection_record_id=inspection.id,
            ),
            db=db,
            current_user=admin,
        )
        assert created.unit_id == unit.id
        assert created.status == "SCHEDULED"
        assert created.cleaning_work_order_id == work_order.id
        assert created.inspection_record_id == inspection.id

        response = Response()
        listed = api.list_turnovers(
            assigned.id, response, db=db, current_user=manager
        )
        assert [row.id for row in listed] == [created.id]
        assert response.headers["cache-control"] == "no-store"

        for bad_payload in (
            _turnover_payload(
                unit.id,
                scheduled_start=datetime(2026, 10, 21, 11, 0),
                scheduled_end=datetime(2026, 10, 21, 15, 0),
                cleaning_work_order_id=foreign_work_order.id,
            ),
            _turnover_payload(
                unit.id,
                scheduled_start=datetime(2026, 10, 22, 11, 0),
                scheduled_end=datetime(2026, 10, 22, 15, 0),
                inspection_record_id=foreign_inspection.id,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                api.create_turnover(
                    assigned.id, bad_payload, db=db, current_user=admin
                )
            assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            api.create_turnover(
                assigned.id,
                _turnover_payload(
                    unit.id,
                    scheduled_start=datetime(2026, 10, 23, 11, 0),
                    scheduled_end=datetime(2026, 10, 23, 15, 0),
                ),
                db=db,
                current_user=manager,
            )
        assert exc.value.status_code == 403

        updated = api.update_turnover(
            assigned.id,
            created.id,
            _turnover_payload(
                unit.id,
                status="COMPLETED",
                cleaning_work_order_id=work_order.id,
                inspection_record_id=inspection.id,
            ),
            db=db,
            current_user=owner,
        )
        assert updated.status == "COMPLETED"

        db.refresh(work_order)
        db.refresh(inspection)
        assert work_order.status == original_work_order_status
        assert inspection.findings == original_inspection_findings

        api.archive_turnover(
            assigned.id, created.id, db=db, current_user=admin
        )
        assert api.list_turnovers(
            assigned.id, Response(), db=db, current_user=admin
        ) == []

        assert db.query(ShortTermRentalTurnover).count() == 1
        assert (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "short_term_rental_turnover")
            .count()
            == 3
        )
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_turnover_validation_duplicate_scope_and_feature_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, _owner, manager, _tenant, _foreign), (assigned, unassigned, _other) = _seed(db)
        unit = _unit(db, assigned.id, "TURN-201")
        api.create_turnover(
            assigned.id, _turnover_payload(unit.id), db=db, current_user=admin
        )

        with pytest.raises(HTTPException) as exc:
            api.create_turnover(
                assigned.id, _turnover_payload(unit.id), db=db, current_user=admin
            )
        assert exc.value.status_code == 409

        with pytest.raises(ValueError):
            _turnover_payload(
                unit.id,
                scheduled_start=datetime(2026, 10, 20, 15, 0),
                scheduled_end=datetime(2026, 10, 20, 11, 0),
            )
        with pytest.raises(ValueError):
            _turnover_payload(unit.id, status="PROVIDER_CONFIRMED")

        with pytest.raises(HTTPException) as exc:
            api.list_turnovers(
                unassigned.id, Response(), db=db, current_user=manager
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=api.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_turnovers(
                assigned.id, Response(), db=db, current_user=admin
            )
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()
