"""Phase 5 preventive-maintenance schedules: tenantless due generation and isolation."""
from datetime import date, timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401
from app.core.database import Base
from app.models.user import Organization, User, UserRole
from app.models.property import Property, Unit, PropertyAssignment
from app.models.work_order import WorkOrder, WorkOrderUpdate
from app.models.audit_log import AuditLog
from app.models.preventive_maintenance import PreventiveMaintenanceSchedule, PreventiveMaintenanceOccurrence
from app.services import preventive_maintenance as pm


def seeded():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    org = Organization(name="Preventive One", slug="preventive-one")
    external = Organization(name="Preventive Other", slug="preventive-other")
    db.add_all([org, external])
    db.flush()

    def make_user(organization, role, label):
        user = User(organization_id=organization.id, role=role, first_name=label,
                    last_name="Maintenance", email=label.lower()+"@pm.example",
                    hashed_password="x", is_active=True)
        db.add(user)
        db.flush()
        return user

    admin = make_user(org, UserRole.ADMIN, "Admin")
    manager = make_user(org, UserRole.MANAGER, "Manager")
    tenant = make_user(org, UserRole.TENANT, "Tenant")
    outsider = make_user(external, UserRole.ADMIN, "Outsider")
    def make_unit(organization, label):
        prop = Property(organization_id=organization.id, name=label,
            address_line1="1 Safety Rd", city="Cleveland", state="OH",
            zip_code="44113", is_active=True)
        db.add(prop)
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="1", is_active=True)
        db.add(unit)
        db.flush()
        return prop, unit

    prop, unit = make_unit(org, "Assigned PM Property")
    hidden, other_unit = make_unit(org, "Unassigned PM Property")
    foreign_prop, foreign_unit = make_unit(external, "Foreign PM Property")
    db.add(PropertyAssignment(property_id=prop.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    db.commit()
    return db, engine, (admin, manager, tenant, outsider), (prop, hidden, foreign_prop), (unit, other_unit, foreign_unit)


def test_preventive_schedule_due_work_order_exactly_once_and_no_tenant_financial_or_entry_rights():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outside = actors
        unit = units[0]
        schedule = pm.create_schedule(db, admin, unit_id=unit.id,
            title="Inspect HVAC filters", description="Perform quarterly equipment inspection",
            interval_days=90, next_due_date=date.today())
        assert schedule.active is True
        assert pm.list_schedules(db, manager)[0].id == schedule.id
        wo, new = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert new is True
        assert wo.tenant_id is None
        assert wo.request_origin == "staff"
        assert wo.requested_by_user_id == admin.id
        assert wo.permission_to_enter is False
        assert wo.total_cost is None
        assert db.query(WorkOrderUpdate).filter_by(work_order_id=wo.id).count() == 1
        occurrence = db.query(PreventiveMaintenanceOccurrence).one()
        assert occurrence.work_order_id == wo.id
        assert occurrence.due_date == date.today()
        assert [record.work_order_id for record in pm.list_occurrences(
            db, admin, schedule.id)] == [wo.id]
        assert [record.work_order_id for record in pm.list_occurrences(
            db, manager, schedule.id)] == [wo.id]
        assert db.query(AuditLog).filter_by(entity_type="preventive_maintenance_occurrence").count() == 1
        creation = db.query(AuditLog).filter_by(entity_type="work_order", entity_id=wo.id,
                                                action="status_transition").one()
        evidence = json.loads(creation.new_value)
        assert evidence["preventive_schedule_id"] == schedule.id
        old, created = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert not created and old.id == wo.id
        assert db.query(WorkOrder).count() == 1
        db.refresh(schedule)
        assert schedule.next_due_date == date.today() + timedelta(days=90)
        pm.set_active(db, admin, schedule.id, False)
        with pytest.raises(HTTPException) as paused:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert paused.value.status_code == 409
        pm.set_active(db, admin, schedule.id, True)
        assert db.query(AuditLog).filter_by(entity_type="preventive_maintenance_schedule").count() == 3
    finally:
        db.close()
        engine.dispose()


def test_preventive_history_omits_corrupted_cross_org_work_order_binding():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outside = actors
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id, title="Review fire safety",
            description="Inspect emergency lighting and signage",
            interval_days=30, next_due_date=date.today(),
        )
        order, created = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert created
        foreign = WorkOrder(
            property_id=props[2].id, unit_id=units[2].id,
            tenant_id=None, request_origin="staff",
            requested_by_user_id=outside.id,
            title="Foreign repair", description="Foreign business evidence",
        )
        db.add(foreign)
        db.flush()
        occurrence = db.query(PreventiveMaintenanceOccurrence).one()
        occurrence.work_order_id = foreign.id
        db.commit()
        assert pm.list_occurrences(db, admin, schedule.id) == []
        assert pm.list_occurrences(db, manager, schedule.id) == []
        with pytest.raises(HTTPException):
            pm.list_occurrences(db, tenant, schedule.id)
        with pytest.raises(HTTPException):
            pm.list_occurrences(db, outside, schedule.id)
    finally:
        db.close()
        engine.dispose()


def test_daily_preventive_due_sweep_catches_up_bounded_without_duplicate_tenants():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outside = actors
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id, title="Inspect window locks",
            description="Quarterly safety walk and window hardware check",
            interval_days=1, next_due_date=date.today(),
        )
        schedule.next_due_date = date.today() - timedelta(days=3)
        db.commit()
        first = pm.sweep_due(db, as_of=date.today(), catchup_limit=2)
        assert first == {"created": 2, "skipped": 0, "backlog": 1}
        second = pm.sweep_due(db, as_of=date.today(), catchup_limit=2)
        assert second == {"created": 2, "skipped": 0, "backlog": 0}
        assert pm.sweep_due(db, as_of=date.today()) == {
            "created": 0, "skipped": 0, "backlog": 0,
        }
        assert db.query(PreventiveMaintenanceOccurrence).count() == 4
        assert db.query(WorkOrder).count() == 4
        assert all(order.tenant_id is None and not order.permission_to_enter
                   and order.total_cost is None for order in db.query(WorkOrder).all())
        assert db.query(AuditLog).filter_by(
            entity_type="preventive_maintenance_occurrence",
            action="generated",
        ).count() == 4
    finally:
        db.close()
        engine.dispose()


def test_daily_preventive_due_sweep_rechecks_creator_authority():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        schedule = pm.create_schedule(
            db, manager, unit_id=units[0].id, title="Review utility room",
            description="Scheduled inspection of utility-room safety devices",
            interval_days=30, next_due_date=date.today(),
        )
        assignment = db.query(PropertyAssignment).filter_by(user_id=manager.id).one()
        assignment.is_active = False
        db.commit()
        result = pm.sweep_due(db, as_of=date.today())
        assert result == {"created": 0, "skipped": 1, "backlog": 1}
        assert db.query(WorkOrder).count() == 0
        assert db.query(PreventiveMaintenanceOccurrence).count() == 0
        with pytest.raises(ValueError):
            pm.sweep_due(db, as_of=date.today() + timedelta(days=1))
    finally:
        db.close()
        engine.dispose()


def test_preventive_schedule_denies_tenants_foreign_org_and_unassigned_manager():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outside = actors
        proper, other, foreign = units
        for actor, target in ((tenant, proper), (outside, proper), (manager, other),
                              (admin, foreign)):
            with pytest.raises(HTTPException):
                pm.create_schedule(db, actor, unit_id=target.id,
                    title="Unauthorized schedule", description="Unauthorized schedule entry",
                    interval_days=30, next_due_date=date.today())
        row = pm.create_schedule(db, admin, unit_id=proper.id,
            title="Inspect fire alarms", description="Inspect and verify smoke detection",
            interval_days=30, next_due_date=date.today())
        for actor in (tenant, outside):
            with pytest.raises(HTTPException):
                pm.generate_due(db, actor, row.id, as_of=date.today())
        with pytest.raises(HTTPException):
            pm.generate_due(db, manager, row.id, as_of=date.today() + timedelta(days=1))
        assert db.query(WorkOrder).count() == 0
        # Lost manager assignment removes visibility and generation rights immediately.
        assignment = db.query(PropertyAssignment).filter_by(user_id=manager.id).one()
        assignment.is_active = False
        db.commit()
        assert pm.list_schedules(db, manager) == []
        with pytest.raises(HTTPException):
            pm.generate_due(db, manager, row.id, as_of=date.today())
        assert db.query(PreventiveMaintenanceOccurrence).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_preventive_daily_job_handler_is_registered():
    from app.jobs import handlers
    from app.jobs.registry import get_job_handler
    assert get_job_handler("maintenance.preventive.generate_due") is (
        handlers.preventive_maintenance_generate_due
    )
