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


def test_replay_never_returns_corrupted_cross_property_work_order():
    db, engine, actors, properties, units = seeded()
    try:
        admin = actors[0]
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Check ventilation", description="Check air handling controls thoroughly",
            interval_days=30, next_due_date=date.today(),
        )
        order, created = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert created
        other_unit = units[2]  # Another organization's property.
        order.unit_id = other_unit.id
        order.property_id = properties[2].id
        db.commit()
        with pytest.raises(HTTPException) as exc:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert exc.value.status_code == 409
        assert db.query(WorkOrder).count() == 1
        assert pm.list_occurrences(db, admin, schedule.id) == []
    finally:
        db.close()
        engine.dispose()


def test_replay_never_discloses_mismatched_occurrence_organization_or_unit():
    db, engine, actors, properties, units = seeded()
    try:
        admin = actors[0]
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Inspect exhaust fans", description="Inspect fan motors and filters safely",
            interval_days=30, next_due_date=date.today(),
        )
        work, fresh = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert fresh
        occurrence = db.query(PreventiveMaintenanceOccurrence).one()
        # Fake a cross-organization occurrence link without changing its work order.
        occurrence.organization_id = actors[3].organization_id
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert blocked.value.status_code == 409
        occurrence.organization_id = admin.organization_id
        # A same-organization but different unit is equally untrusted.
        work.unit_id = units[1].id
        work.property_id = properties[1].id
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert blocked.value.status_code == 409
        assert pm.list_occurrences(db, admin, schedule.id) == []
        assert db.query(WorkOrder).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_corrupted_latest_occurrence_cannot_fall_back_to_older_clean_order():
    db, engine, actors, properties, units = seeded()
    try:
        admin = actors[0]
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Inspect roof drains", description="Review drains and rooftop water paths",
            interval_days=1, next_due_date=date.today(),
        )
        schedule.next_due_date = date.today() - timedelta(days=1)
        db.commit()
        first, fresh = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert fresh
        recent, fresh = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert fresh and recent.id != first.id
        latest = db.query(PreventiveMaintenanceOccurrence).filter_by(
            work_order_id=recent.id,
        ).one()
        latest.organization_id = actors[3].organization_id
        db.commit()
        with pytest.raises(HTTPException) as exc:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert exc.value.status_code == 409
        assert db.query(WorkOrder).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_preview_due_is_scoped_read_only_bounded_and_end_date_aware():
    db, engine, actors, properties, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        row = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Check gutters", description="Inspect rooftop drainage channels",
            interval_days=1, next_due_date=date.today(),
            end_date=date.today() + timedelta(days=1),
        )
        # Advance as-of is prohibited; preview only shows actions due as of now.
        row.next_due_date = date.today() - timedelta(days=3)
        db.commit()
        result = pm.preview_due(db, manager, row.id, as_of=date.today(), limit=2)
        assert result["due_dates"] == [
            date.today() - timedelta(days=3),
            date.today() - timedelta(days=2),
        ]
        assert result["has_more"] is True
        result = pm.preview_due(db, admin, row.id, as_of=date.today(), limit=12)
        assert result["due_dates"] == [
            date.today() - timedelta(days=n) for n in (3, 2, 1, 0)
        ]
        assert result["has_more"] is False
        assert db.query(WorkOrder).count() == 0
        assert db.query(PreventiveMaintenanceOccurrence).count() == 0
        pm.set_active(db, admin, row.id, False)
        assert pm.preview_due(db, manager, row.id, as_of=date.today())["due_dates"] == []
        for actor in (tenant, outsider):
            with pytest.raises(HTTPException):
                pm.preview_due(db, actor, row.id, as_of=date.today())
        with pytest.raises(HTTPException) as future:
            pm.preview_due(db, admin, row.id, as_of=date.today() + timedelta(days=1))
        assert future.value.status_code == 422
    finally:
        db.close()
        engine.dispose()


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


def test_schedule_settings_pause_only_atomic_audit_and_preserve_due():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        schedule = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Check filters", description="Inspect HVAC ventilation and filters",
            interval_days=30, next_due_date=date.today())
        with pytest.raises(HTTPException) as exc:
            pm.update_settings(db, admin, schedule.id, interval_days=45)
        assert exc.value.status_code == 409
        pm.set_active(db, manager, schedule.id, False)
        original_due = schedule.next_due_date
        edited = pm.update_settings(db, manager, schedule.id,
            title="Review HVAC", description="Inspect air handlers and filters",
            interval_days=45)
        assert edited.title == "Review HVAC"
        assert edited.next_due_date == original_due
        assert edited.active is False
        audit = db.query(AuditLog).filter_by(
            entity_type="preventive_maintenance_schedule", entity_id=schedule.id,
            action="settings_changed").one()
        assert audit.user_id == manager.id
        assert json.loads(audit.old_value)["interval_days"] == 30
        assert json.loads(audit.new_value)["interval_days"] == 45
        pm.update_settings(db, manager, schedule.id, interval_days=45)
        assert db.query(AuditLog).filter_by(action="settings_changed").count() == 1
        for actor in (tenant, outsider):
            with pytest.raises(HTTPException):
                pm.update_settings(db, actor, schedule.id, interval_days=60)
        for args in ({}, {"title": " "}, {"interval_days": 0}):
            with pytest.raises(HTTPException) as invalid:
                pm.update_settings(db, admin, schedule.id, **args)
            assert invalid.value.status_code == 422
        pm.set_active(db, admin, schedule.id, True)
        wo, new = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert new is True
        assert wo.tenant_id is None and wo.total_cost is None
        db.refresh(schedule)
        assert schedule.next_due_date == original_due + timedelta(days=45)
    finally:
        db.close()
        engine.dispose()


def test_schedule_settings_revoked_manager_cannot_edit():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        schedule = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Review alarms", description="Inspect smoke alarms and safety signage",
            interval_days=30, next_due_date=date.today())
        pm.set_active(db, admin, schedule.id, False)
        assignment = db.query(PropertyAssignment).filter_by(
            user_id=manager.id, property_id=props[0].id).one()
        assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException):
            pm.update_settings(db, manager, schedule.id, title="Unauthorized")
        db.refresh(schedule)
        assert schedule.title == "Review alarms"
        assert db.query(AuditLog).filter_by(action="settings_changed").count() == 0
    finally:
        db.close()
        engine.dispose()


def test_pause_resumes_from_fresh_row_and_audits_only_actual_change():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        row = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Inspect ventilation", description="Inspect all ventilation devices and filters",
            interval_days=30, next_due_date=date.today())
        other = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            cached = other.get(PreventiveMaintenanceSchedule, row.id)
            assert cached.active is True
            pm.set_active(db, admin, row.id, False)
            assert cached.active is True
            # A stale session must read the now-paused row under the lock:
            # retrying pause cannot create duplicate audit activity.
            pm.set_active(other, manager, row.id, False)
            other.refresh(cached)
            assert cached.active is False
        finally:
            other.close()
        assert db.query(AuditLog).filter_by(
            entity_type="preventive_maintenance_schedule",
            action="active_changed",
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_schedule_end_date_bounds_due_sweep_and_replay():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        row = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Check fire exits", description="Confirm exit doors and signs are clear",
            interval_days=1, next_due_date=date.today(),
            end_date=date.today())
        row.next_due_date = date.today() - timedelta(days=2)
        db.commit()
        summary = pm.sweep_due(db, as_of=date.today(), catchup_limit=12)
        assert summary == {"created": 3, "skipped": 0, "backlog": 0}
        assert db.query(PreventiveMaintenanceOccurrence).count() == 3
        assert all(order.tenant_id is None and order.total_cost is None
                   for order in db.query(WorkOrder).all())
        last, fresh = pm.generate_due(db, admin, row.id, as_of=date.today())
        assert fresh is False
        assert last.id == pm.list_occurrences(db, admin, row.id)[0].work_order_id
        assert pm.sweep_due(db, as_of=date.today()) == {
            "created": 0, "skipped": 0, "backlog": 0,
        }
        pm.set_active(db, admin, row.id, False)
        changed = pm.update_settings(db, manager, row.id, end_date=None)
        assert changed.end_date is None
        audit = db.query(AuditLog).filter_by(
            entity_type="preventive_maintenance_schedule", action="settings_changed",
        ).one()
        assert json.loads(audit.old_value)["end_date"] == date.today().isoformat()
        assert json.loads(audit.new_value)["end_date"] is None
        pm.set_active(db, manager, row.id, True)
        more, fresh = pm.generate_due(db, admin, row.id, as_of=date.today())
        assert fresh is False
        assert more.id == last.id
    finally:
        db.close()
        engine.dispose()


def test_schedule_end_date_validated_on_create_and_pause_only_edit():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        with pytest.raises(HTTPException) as invalid:
            pm.create_schedule(db, admin, unit_id=units[0].id,
                title="Bad end date", description="Schedule would end before starting",
                interval_days=30, next_due_date=date.today() + timedelta(days=3),
                end_date=date.today() + timedelta(days=2))
        assert invalid.value.status_code == 422
        row = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Review equipment", description="Check all safety equipment",
            interval_days=30, next_due_date=date.today())
        with pytest.raises(HTTPException) as running:
            pm.update_settings(db, admin, row.id, end_date=date.today())
        assert running.value.status_code == 409
        pm.set_active(db, admin, row.id, False)
        with pytest.raises(HTTPException) as historical:
            pm.update_settings(db, admin, row.id, end_date=date.today()-timedelta(days=1))
        assert historical.value.status_code == 422
        assert pm.update_settings(db, admin, row.id, end_date=date.today()).end_date == date.today()
    finally:
        db.close()
        engine.dispose()


def test_retired_inventory_retains_scoped_history_but_disables_generation():
    db, engine, actors, props, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        row = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Review shutoff valves", description="Check valves and emergency hardware",
            interval_days=30, next_due_date=date.today())
        work, fresh = pm.generate_due(db, admin, row.id, as_of=date.today())
        assert fresh
        props[0].is_active = False
        units[0].is_active = False
        db.commit()
        assert [x.id for x in pm.list_schedules(db, admin)] == [row.id]
        assert [x.id for x in pm.list_schedules(db, manager)] == [row.id]
        assert pm.read_schedule(db, admin, row.id).id == row.id
        assert pm.list_occurrences(db, manager, row.id)[0].work_order_id == work.id
        with pytest.raises(HTTPException):
            pm.generate_due(db, admin, row.id, as_of=date.today())
        with pytest.raises(HTTPException):
            pm.set_active(db, admin, row.id, False)
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=manager.id,
        ).one()
        assignment.is_active = False
        db.commit()
        assert pm.list_schedules(db, manager) == []
        with pytest.raises(HTTPException):
            pm.list_occurrences(db, manager, row.id)
        with pytest.raises(HTTPException):
            pm.read_schedule(db, outsider, row.id)
        with pytest.raises(HTTPException):
            pm.read_schedule(db, tenant, row.id)
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
        assert [row.due_date for row in pm.list_occurrences(
            db, admin, schedule.id, limit=1, offset=1,
        )] == [date.today() - timedelta(days=1)]
        assert [row.due_date for row in pm.list_occurrences(
            db, manager, schedule.id, limit=2, offset=2,
        )] == [date.today() - timedelta(days=2), date.today() - timedelta(days=3)]
        with pytest.raises(HTTPException):
            pm.list_occurrences(db, tenant, schedule.id, limit=1, offset=1)

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


def test_generate_due_refreshes_current_schedule_after_another_session_updates_date():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outside = actors
        schedule = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Review boiler safety", description="Inspect boiler room safety equipment",
            interval_days=30, next_due_date=date.today())
        # Simulate another worker moving the due date after this session cached it.
        other_session = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            updated = other_session.get(PreventiveMaintenanceSchedule, schedule.id)
            updated.next_due_date = date.today() + timedelta(days=1)
            other_session.commit()
        finally:
            other_session.close()
        assert schedule.next_due_date == date.today()
        with pytest.raises(HTTPException) as not_due:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert not_due.value.status_code == 409
        assert db.query(WorkOrder).count() == 0
        assert db.query(PreventiveMaintenanceOccurrence).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_schedule_list_is_bounded_and_excludes_unassigned_properties():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outside = actors
        older = pm.create_schedule(db, admin, unit_id=units[0].id,
            title="Inspect garage", description="Monthly garage safety inspection",
            interval_days=30, next_due_date=date.today())
        newer = pm.create_schedule(db, admin, unit_id=units[1].id,
            title="Inspect basement", description="Monthly basement safety inspection",
            interval_days=30, next_due_date=date.today())
        assert [s.id for s in pm.list_schedules(db, admin, limit=1)] == [newer.id]
        assert [s.id for s in pm.list_schedules(db, admin, limit=1, offset=1)] == [older.id]
        assert [s.id for s in pm.list_schedules(db, manager)] == [older.id]
        assert pm.list_schedules(db, outside) == []
        with pytest.raises(HTTPException):
            pm.list_schedules(db, tenant)
        with pytest.raises(HTTPException):
            pm.list_schedules(db, admin, limit=101)
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
