"""Phase 5 bounded work-order queue filters never expand a user's visibility."""
from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401 - import complete model registry
from app.core.database import Base
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderCategory, WorkOrderPriority, WorkOrderUpdate
from app.routers.work_orders import (list_work_orders, work_order_queue_summary, _user_can_access_work_order, start_work_order, complete_work_order, update_work_order, assign_work_order, submit_work_order, acknowledge_work_order, add_comment, requestable_work_order_units, possible_duplicate_work_orders)
from app.models.audit_log import AuditLog
from app.routers.properties import check_property_access, visible_properties_query
from app.routers.users import assign_user_to_property, list_assignments, remove_assignment
from app.models.lease import Lease, LeaseStatus
from app.schemas.work_order import WorkOrderComplete, WorkOrderUpdateFields, WorkOrderAssign, WorkOrderCreate, WorkOrderComment
from fastapi import HTTPException
import pytest


def _seed_queue():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    own_org = Organization(name="Queue One", slug="queue-one")
    external_org = Organization(name="Queue Two", slug="queue-two")
    db.add_all([own_org, external_org])
    db.flush()

    def actor(org, role, name):
        row = User(
            organization_id=org.id, role=role, first_name=name, last_name="Tester",
            email=f"{name.lower()}@queue.example", hashed_password="test", is_active=True,
        )
        db.add(row)
        db.flush()
        return row

    admin = actor(own_org, UserRole.ADMIN, "QueueAdmin")
    manager = actor(own_org, UserRole.MANAGER, "QueueManager")
    tenant = actor(own_org, UserRole.TENANT, "QueueTenant")
    other_tenant = actor(own_org, UserRole.TENANT, "OtherTenant")
    crew = actor(own_org, UserRole.CREW, "QueueCrew")
    external_admin = actor(external_org, UserRole.ADMIN, "OutsideAdmin")
    external_tenant = actor(external_org, UserRole.TENANT, "OutsideTenant")

    def location(org, name):
        prop = Property(
            organization_id=org.id, name=name, address_line1="100 Test Street",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(prop)
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="A1", bedrooms=1, bathrooms=1, monthly_rent=800)
        db.add(unit)
        db.flush()
        return prop, unit

    p1, u1 = location(own_org, "Assigned Property")
    p2, u2 = location(own_org, "Other Property")
    p3, u3 = location(external_org, "External Property")
    db.add(PropertyAssignment(
        property_id=p1.id, user_id=manager.id, role=UserRole.MANAGER, is_active=True,
    ))
    db.add(PropertyAssignment(
        property_id=p1.id, user_id=crew.id, role=UserRole.CREW, is_active=True,
    ))
    # Deliberately malformed cross-organization assignment: a manager may not
    # acquire another organization's work order even with a rogue assignment.
    db.add(PropertyAssignment(
        property_id=p3.id, user_id=manager.id, role=UserRole.MANAGER, is_active=True,
    ))
    db.flush()

    def order(prop, unit, resident, title, priority, category,
              status=WorkOrderStatus.SUBMITTED, assigned=None):
        row = WorkOrder(
            property_id=prop.id, unit_id=unit.id, tenant_id=resident.id,
            title=title, description="Work order issue details", priority=priority,
            category=category, status=status, assigned_to_id=assigned,
            created_at=datetime(2026, 10, 18, 12, 0),
        )
        db.add(row)
        db.flush()
        return row

    a = order(p1, u1, tenant, "100% water pressure", WorkOrderPriority.HIGH, WorkOrderCategory.PLUMBING, assigned=crew.id)
    b = order(p1, u1, tenant, "100X water pressure", WorkOrderPriority.LOW, WorkOrderCategory.GENERAL)
    c = order(p2, u2, other_tenant, "Outside assigned properties", WorkOrderPriority.EMERGENCY, WorkOrderCategory.ELECTRICAL)
    d = order(p3, u3, external_tenant, "Outside organization", WorkOrderPriority.EMERGENCY, WorkOrderCategory.HVAC)
    # Deliberately bogus foreign-property tenant/crew references. The unit's
    # actual organization always wins over these mismatched user IDs.
    d.tenant_id = tenant.id
    d.assigned_to_id = crew.id
    db.commit()
    return db, engine, (admin, manager, tenant, other_tenant, crew, external_admin), (p1, p2, p3), (a, b, c, d)


def _queue(db, user, **filters):
    return list_work_orders(
        status=filters.get("status"),
        priority=filters.get("priority"),
        category=filters.get("category"),
        property_id=filters.get("property_id"),
        search=filters.get("search"),
        limit=filters.get("limit"),
        offset=filters.get("offset", 0),
        db=db,
        current_user=user,
    )


def test_queue_filters_and_deterministic_paging():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin = actors[0]
        p1 = properties[0]
        a, b, c, d = orders
        assert [item.id for item in _queue(db, admin)] == [c.id, b.id, a.id]
        assert [item.id for item in _queue(db, admin, priority=WorkOrderPriority.HIGH)] == [a.id]
        assert [item.id for item in _queue(db, admin, category=WorkOrderCategory.GENERAL)] == [b.id]
        assert [item.id for item in _queue(db, admin, property_id=p1.id)] == [b.id, a.id]
        assert [item.id for item in _queue(db, admin, search="100%")] == [a.id]
        assert [item.id for item in _queue(db, admin, search="100_")] == []
        assert [item.id for item in _queue(db, admin, search="water")] == [b.id, a.id]
        assert [item.id for item in _queue(db, admin, limit=1, offset=1)] == [b.id]
        assert [item.id for item in _queue(db, admin, limit=1, offset=2)] == [a.id]
        assert not _queue(db, admin, status=WorkOrderStatus.CLOSED)
        assert d.id not in [item.id for item in _queue(db, admin)]
    finally:
        db.close()
        engine.dispose()


def test_queue_never_crosses_manager_tenant_crew_or_organization_scope():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, external_admin = actors
        a, b, c, d = orders
        assert [item.id for item in _queue(db, manager)] == [b.id, a.id]
        assert _queue(db, manager, search="Outside") == []
        assert _user_can_access_work_order(db, manager, a) is True
        assert _user_can_access_work_order(db, manager, d) is False
        assert [item.id for item in _queue(db, tenant)] == [b.id, a.id]
        assert [item.id for item in _queue(db, other_tenant)] == [c.id]
        assert [item.id for item in _queue(db, crew)] == [a.id]
        assert _user_can_access_work_order(db, tenant, d) is False
        assert _user_can_access_work_order(db, crew, d) is False
        assert [item.id for item in _queue(db, external_admin)] == [d.id]
        assert _queue(db, external_admin, property_id=properties[0].id) == []
        assert _queue(db, tenant, property_id=properties[1].id) == []
    finally:
        db.close()
        engine.dispose()


def test_rogue_cross_organization_crew_id_cannot_start_or_complete():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        crew = actors[4]
        foreign_work_order = orders[3]
        assert foreign_work_order.assigned_to_id == crew.id
        foreign_work_order.status = WorkOrderStatus.ASSIGNED
        db.commit()
        with pytest.raises(HTTPException) as blocked_start:
            start_work_order(foreign_work_order.id, db=db, current_user=crew)
        assert blocked_start.value.status_code == 403
        assert db.get(WorkOrder, foreign_work_order.id).status == WorkOrderStatus.ASSIGNED

        foreign_work_order.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        with pytest.raises(HTTPException) as blocked_completion:
            complete_work_order(
                foreign_work_order.id, WorkOrderComplete(resolution_notes="Must not write"),
                db=db, current_user=crew,
            )
        assert blocked_completion.value.status_code == 403
        assert db.get(WorkOrder, foreign_work_order.id).status == WorkOrderStatus.IN_PROGRESS
        assert db.get(WorkOrder, foreign_work_order.id).resolution_notes is None
    finally:
        db.close()
        engine.dispose()


def test_work_order_edit_logs_atomic_before_after_and_rejects_status_bypass():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin = actors[0]
        order = orders[0]
        previous_title = order.title
        result = update_work_order(
            order.id, WorkOrderUpdateFields(title="Verified edited description"),
            db=db, current_user=admin,
        )
        assert result.title == "Verified edited description"
        event = db.query(AuditLog).filter(
            AuditLog.entity_type == "work_order",
            AuditLog.entity_id == order.id,
            AuditLog.action == "updated",
        ).one()
        assert previous_title in event.old_value
        assert "Verified edited description" in event.new_value

        with pytest.raises(HTTPException) as forbidden:
            update_work_order(
                order.id, WorkOrderUpdateFields(status=WorkOrderStatus.CLOSED),
                db=db, current_user=admin,
            )
        assert forbidden.value.status_code == 409
        assert db.get(WorkOrder, order.id).status == WorkOrderStatus.SUBMITTED
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "work_order", AuditLog.entity_id == order.id,
            AuditLog.action == "updated",
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_assign_work_order_requires_acknowledged_status_and_authorized_active_crew():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, _manager, _tenant, _other_tenant, crew, _foreign = actors
        order = orders[0]
        with pytest.raises(HTTPException) as premature:
            assign_work_order(order.id, WorkOrderAssign(crew_user_id=crew.id),
                              db=db, current_user=admin)
        assert premature.value.status_code == 409
        assert order.assigned_to_id == crew.id  # originally assigned by seed
        order.status = WorkOrderStatus.ACKNOWLEDGED
        order.assigned_to_id = None
        db.commit()
        assigned = assign_work_order(
            order.id, WorkOrderAssign(crew_user_id=crew.id),
            db=db, current_user=admin,
        )
        assert assigned.status == WorkOrderStatus.ASSIGNED
        assert assigned.assigned_to_id == crew.id
        repeated = assign_work_order(
            order.id, WorkOrderAssign(crew_user_id=crew.id),
            db=db, current_user=admin,
        )
        assert repeated.id == assigned.id
        order.status = WorkOrderStatus.CLOSED
        db.commit()
        with pytest.raises(HTTPException) as finished:
            assign_work_order(order.id, WorkOrderAssign(crew_user_id=crew.id),
                              db=db, current_user=admin)
        assert finished.value.status_code == 409
    finally:
        db.close()
        engine.dispose()


def test_work_order_creation_and_acknowledgement_have_one_durable_activity_each():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin = actors[0]
        created = submit_work_order(
            WorkOrderCreate(
                unit_id=orders[0].unit_id,
                title="Review tenant concern",
                description="Unit requires prompt staff review.",
            ),
            db=db, current_user=admin,
        )
        history = db.query(WorkOrderUpdate).filter(
            WorkOrderUpdate.work_order_id == created.id
        ).all()
        assert len(history) == 1
        assert history[0].to_status == WorkOrderStatus.SUBMITTED

        reviewed = acknowledge_work_order(created.id, db=db, current_user=admin)
        assert reviewed.status == WorkOrderStatus.ACKNOWLEDGED
        events = db.query(WorkOrderUpdate).filter(
            WorkOrderUpdate.work_order_id == created.id
        ).order_by(WorkOrderUpdate.id.asc()).all()
        assert len(events) == 2
        assert events[1].from_status == WorkOrderStatus.SUBMITTED
        assert events[1].to_status == WorkOrderStatus.ACKNOWLEDGED
    finally:
        db.close()
        engine.dispose()


def test_valid_property_assigned_crew_can_start_and_complete_with_audit():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        crew = actors[4]
        order = orders[0]
        assert order.assigned_to_id == crew.id
        order.status = WorkOrderStatus.ASSIGNED
        db.commit()
        started = start_work_order(order.id, db=db, current_user=crew)
        assert started.status == WorkOrderStatus.IN_PROGRESS
        completed = complete_work_order(
            order.id, WorkOrderComplete(resolution_notes="Repaired and inspected"),
            db=db, current_user=crew,
        )
        assert completed.status == WorkOrderStatus.COMPLETED
        assert completed.resolution_notes == "Repaired and inspected"
        events = db.query(WorkOrderUpdate).filter(
            WorkOrderUpdate.work_order_id == order.id
        ).order_by(WorkOrderUpdate.id.asc()).all()
        assert [(event.from_status, event.to_status) for event in events[-2:]] == [
            (WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS),
            (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED),
        ]
    finally:
        db.close()
        engine.dispose()


def test_status_and_comment_audit_is_scoped_and_idempotent():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin = actors[0]
        created = submit_work_order(
            WorkOrderCreate(unit_id=orders[0].unit_id, title="Repair review",
                            description="Please check the reported water pressure."),
            db=db, current_user=admin,
        )
        acknowledge_work_order(created.id, db=db, current_user=admin)
        comment = add_comment(created.id, WorkOrderComment(message="Repair followup"),
                              db=db, current_user=admin)
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "work_order", AuditLog.entity_id == created.id,
        ).order_by(AuditLog.id).all()
        assert [e.action for e in audit] == [
            "status_transition", "status_transition", "comment_added"
        ]
        assert all(e.organization_id == admin.organization_id for e in audit)
        assert all(e.user_id == admin.id for e in audit)
        assert '"status":null' in audit[0].old_value
        assert '"status":"acknowledged"' in audit[1].new_value
        assert f'"activity_id":{comment.id}' in audit[2].new_value
        assert "Repair followup" not in audit[2].new_value
        with pytest.raises(HTTPException):
            acknowledge_work_order(created.id, db=db, current_user=admin)
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "work_order", AuditLog.entity_id == created.id
        ).count() == 3
    finally:
        db.close()
        engine.dispose()


def test_assignment_audit_records_previous_and_next_crew_once():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, other, crew, foreign = actors
        wo = orders[0]
        wo.status = WorkOrderStatus.ACKNOWLEDGED
        wo.assigned_to_id = None
        db.commit()
        assign_work_order(wo.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=admin)
        rows = db.query(AuditLog).filter(
            AuditLog.entity_type == "work_order", AuditLog.entity_id == wo.id
        ).order_by(AuditLog.id).all()
        assert [row.action for row in rows] == [
            "status_transition", "crew_assignment"
        ]
        assert '"assigned_to_id":null' in rows[1].old_value
        assert f'"assigned_to_id":{crew.id}' in rows[1].new_value
        assign_work_order(wo.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=admin)
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "work_order", AuditLog.entity_id == wo.id
        ).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_queue_summary_enforces_roles_and_actual_property_organization():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outside = actors
        a, b, c, d = orders
        a.status = WorkOrderStatus.ACKNOWLEDGED
        a.assigned_to_id = None
        b.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        assert work_order_queue_summary(db=db, current_user=admin) == {
            "open": 3, "emergency_open": 1, "awaiting_assignment": 1,
            "in_progress": 1, "ready_to_close": 0,
        }
        manager_counts = work_order_queue_summary(db=db, current_user=manager)
        assert manager_counts == {
            "open": 2, "emergency_open": 0, "awaiting_assignment": 1,
            "in_progress": 1, "ready_to_close": 0,
        }
        assert work_order_queue_summary(db=db, current_user=tenant) == manager_counts
        assert work_order_queue_summary(db=db, current_user=crew)["open"] == 0
        assert work_order_queue_summary(db=db, current_user=other_tenant)["open"] == 1
        assert work_order_queue_summary(db=db, current_user=outside)["emergency_open"] == 1
        c.status = WorkOrderStatus.COMPLETED
        db.commit()
        assert work_order_queue_summary(db=db, current_user=admin)["ready_to_close"] == 1
        assert work_order_queue_summary(db=db, current_user=manager)["ready_to_close"] == 0
    finally:
        db.close()
        engine.dispose()


def test_maintenance_intake_units_enforce_lease_and_actual_organization():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other, crew, foreign = actors
        p1, p2, p3 = properties
        u1, u2, u3 = [orders[i].unit_id for i in (0, 2, 3)]
        for uid in (u1, u3):
            db.add(Lease(
                unit_id=uid, tenant_id=tenant.id, status=LeaseStatus.ACTIVE,
                start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
                monthly_rent=900, security_deposit=900,
            ))
        db.commit()
        def allowed(user, **kw):
            return requestable_work_order_units(
                search=kw.get("search"), limit=kw.get("limit", 50),
                offset=kw.get("offset", 0), db=db, current_user=user,
            )
        assert [item["id"] for item in allowed(tenant)] == [u1]
        assert {item["id"] for item in allowed(manager)} == {u1}
        assert {item["id"] for item in allowed(admin)} == {u1, u2}
        assert [item["id"] for item in allowed(foreign)] == [u3]
        assert allowed(crew) == []
        assert allowed(tenant, search="no-match") == []
        assert allowed(admin, limit=1, offset=0) != allowed(admin, limit=1, offset=1)
        with pytest.raises(HTTPException) as crossed:
            submit_work_order(
                WorkOrderCreate(unit_id=u3, title="Out of scope",
                                description="Wrong organization unit."),
                db=db, current_user=tenant,
            )
        assert crossed.value.status_code == 403
        with pytest.raises(HTTPException) as staff_crossed:
            submit_work_order(
                WorkOrderCreate(unit_id=u3, title="Other scope",
                                description="Wrong organization property."),
                db=db, current_user=admin,
            )
        assert staff_crossed.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_possible_duplicate_intake_never_exposes_unrelated_work_orders():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outside = actors
        a, b, c, d = orders

        def search(user, unit, term):
            return possible_duplicate_work_orders(
                unit_id=unit, title=term, db=db, current_user=user
            )

        assert [item["id"] for item in search(admin, a.unit_id, "100")] == [b.id, a.id]
        assert [item["id"] for item in search(manager, a.unit_id, "100")] == [b.id, a.id]
        assert [item["id"] for item in search(tenant, a.unit_id, "100")] == [b.id, a.id]
        assert [item["id"] for item in search(crew, a.unit_id, "100")] == [a.id]
        assert search(other_tenant, a.unit_id, "100") == []
        assert search(outside, a.unit_id, "100") == []
        assert search(tenant, d.unit_id, "Outside") == []
        assert [item["id"] for item in search(admin, a.unit_id, "100%")] == [a.id]

        a.status = WorkOrderStatus.CLOSED
        b.status = WorkOrderStatus.CANCELLED
        db.commit()
        assert search(admin, a.unit_id, "100") == []
        with pytest.raises(HTTPException) as invalid:
            search(admin, a.unit_id, "   ")
        assert invalid.value.status_code == 422
    finally:
        db.close()
        engine.dispose()


def test_authorized_tenant_and_manager_intake_succeeds_but_crew_cannot_submit():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outside = actors
        from app.models.lease import Lease, LeaseStatus
        from datetime import date
        db.add(Lease(
            unit_id=orders[0].unit_id, tenant_id=tenant.id,
            status=LeaseStatus.ACTIVE,
            start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
            monthly_rent=850, security_deposit=850,
        ))
        db.commit()
        resident_request = submit_work_order(
            WorkOrderCreate(
                unit_id=orders[0].unit_id, title="Tenant plumbing request",
                description="Kitchen faucet water pressure dropped.",
            ),
            db=db, current_user=tenant,
        )
        assert resident_request.tenant_id == tenant.id
        staff_request = submit_work_order(
            WorkOrderCreate(
                unit_id=orders[0].unit_id, title="Manager inspection request",
                description="Inspect the kitchen sink for leakage.",
            ),
            db=db, current_user=manager,
        )
        assert staff_request.property_id == props[0].id
        assert [row.id for row in _queue(db, tenant) if row.id == resident_request.id] == [resident_request.id]
        with pytest.raises(HTTPException) as forbidden:
            submit_work_order(
                WorkOrderCreate(
                    unit_id=orders[0].unit_id, title="Crew not allowed",
                    description="Crew cannot submit on behalf of tenant.",
                ),
                db=db, current_user=crew,
            )
        assert forbidden.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_inactive_or_deleted_unit_never_enters_new_request_picker():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin = actors[0]
        unit = db.get(Unit, orders[0].unit_id)
        assert unit is not None
        prop = props[0]

        def assert_unavailable():
            choices = requestable_work_order_units(
                search=None, limit=50, offset=0, db=db, current_user=admin,
            )
            assert unit.id not in {row["id"] for row in choices}
            with pytest.raises(HTTPException) as blocked:
                submit_work_order(
                    WorkOrderCreate(
                        unit_id=unit.id, title="Unavailable unit repair",
                        description="The unit or property is not available.",
                    ),
                    db=db, current_user=admin,
                )
            assert blocked.value.status_code == 404

        for target, field, blocked_value, restored_value in (
            (unit, "is_active", False, True),
            (unit, "deleted_at", datetime(2026, 10, 18), None),
            (prop, "is_active", False, True),
            (prop, "deleted_at", datetime(2026, 10, 18), None),
        ):
            setattr(target, field, blocked_value)
            db.commit()
            assert_unavailable()
            setattr(target, field, restored_value)
            db.commit()
    finally:
        db.close()
        engine.dispose()


def test_soft_deleted_manager_assignment_cannot_select_request_units():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager = actors[:2]
        property_id = properties[0].id
        unit_id = orders[0].unit_id

        def picker(user):
            return requestable_work_order_units(
                search=None, limit=50, offset=0, db=db, current_user=user,
            )

        assert unit_id in {row["id"] for row in picker(manager)}
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=property_id, user_id=manager.id,
        ).one()
        assignment.deleted_at = datetime(2026, 10, 18, 12)
        db.commit()

        # An assignment whose access has been deleted is not authority
        # even if a stale is_active flag remains True.
        assert unit_id not in {row["id"] for row in picker(manager)}
        assert unit_id in {row["id"] for row in picker(admin)}
    finally:
        db.close()
        engine.dispose()


def test_cross_org_and_soft_deleted_staff_assignment_cannot_authorize_property_or_work_orders():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, external_admin = actors
        own_property, _, foreign_property = properties
        own_order = orders[0]
        with pytest.raises(HTTPException) as crossed:
            check_property_access(db, manager, foreign_property.id)
        assert crossed.value.status_code == 403
        assert {row.id for row in visible_properties_query(db, manager).all()} == {own_property.id}

        for staff in (manager, crew):
            assignment = db.query(PropertyAssignment).filter_by(
                property_id=own_property.id, user_id=staff.id,
            ).one()
            assignment.deleted_at = datetime(2026, 10, 18, 12)
        db.commit()
        for staff in (manager, crew):
            with pytest.raises(HTTPException) as revoked:
                check_property_access(db, staff, own_property.id)
            assert revoked.value.status_code == 403
            assert visible_properties_query(db, staff).all() == []
            assert _queue(db, staff) == []
            assert _user_can_access_work_order(db, staff, own_order) is False

        with pytest.raises(HTTPException) as blocked_submission:
            submit_work_order(
                WorkOrderCreate(unit_id=own_order.unit_id, title="No assignment",
                                description="Revoked manager may not file here."),
                db=db, current_user=manager,
            )
        assert blocked_submission.value.status_code == 403

        own_order.status = WorkOrderStatus.ASSIGNED
        db.commit()
        with pytest.raises(HTTPException) as blocked_start:
            start_work_order(own_order.id, db=db, current_user=crew)
        assert blocked_start.value.status_code == 403

        own_order.status = WorkOrderStatus.ACKNOWLEDGED
        own_order.assigned_to_id = None
        db.commit()
        with pytest.raises(HTTPException) as blocked_assignment:
            assign_work_order(own_order.id, WorkOrderAssign(crew_user_id=crew.id),
                              db=db, current_user=admin)
        assert blocked_assignment.value.status_code == 400
    finally:
        db.close()
        engine.dispose()


def test_property_assignment_reactivation_and_roster_fail_closed():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        own_property, _, foreign_property = properties
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=own_property.id, user_id=crew.id,
        ).one()
        assignment.is_active = True
        assignment.deleted_at = datetime(2026, 10, 18, 12)
        db.commit()

        assert crew.id not in {row["user_id"] for row in list_assignments(
            own_property.id, db=db, current_user=admin,
        )}
        assert manager.id not in {row["user_id"] for row in list_assignments(
            foreign_property.id, db=db, current_user=foreign_admin,
        )}

        revived = assign_user_to_property(
            own_property.id, crew.id, db=db, current_user=admin,
        )
        assert revived["status"] == "already_assigned"
        assert assignment.is_active is True and assignment.deleted_at is None
        assert crew.id in {row["user_id"] for row in list_assignments(
            own_property.id, db=db, current_user=admin,
        )}

        crew.is_active = False
        db.commit()
        assert crew.id not in {row["user_id"] for row in list_assignments(
            own_property.id, db=db, current_user=admin,
        )}
        with pytest.raises(HTTPException) as inactive:
            assign_user_to_property(
                own_property.id, crew.id, db=db, current_user=admin,
            )
        assert inactive.value.status_code == 400
    finally:
        db.close()
        engine.dispose()


def test_soft_deleted_crew_user_cannot_be_assigned_even_if_active_flag_remains():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, _manager, _tenant, _other, crew, _foreign = actors
        wo = orders[0]
        wo.status = WorkOrderStatus.ACKNOWLEDGED
        wo.assigned_to_id = None
        # A stale is_active flag must not permit assigning a deleted account.
        crew.is_active = True
        crew.deleted_at = datetime(2026, 10, 18, 12)
        db.commit()
        with pytest.raises(HTTPException) as denied:
            assign_work_order(
                wo.id, WorkOrderAssign(crew_user_id=crew.id),
                db=db, current_user=admin,
            )
        assert denied.value.status_code == 400
        assert wo.assigned_to_id is None
        assert wo.status == WorkOrderStatus.ACKNOWLEDGED
    finally:
        db.close()
        engine.dispose()


def test_property_staff_assignment_audits_create_revoke_reactivate_and_noops():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        own_property = properties[0]
        second_property = properties[1]

        created = assign_user_to_property(
            second_property.id, crew.id, db=db, current_user=admin,
        )
        assignment_id = created["assignment_id"]
        created_logs = db.query(AuditLog).filter_by(
            entity_type="property_assignment", entity_id=assignment_id,
        ).all()
        assert len(created_logs) == 1
        assert created_logs[0].action == "created"
        assert created_logs[0].user_id == admin.id
        assert created_logs[0].organization_id == admin.organization_id
        assert json.loads(created_logs[0].new_value)["user_id"] == crew.id

        assert remove_assignment(assignment_id, db=db, current_user=admin) is None
        revoked_logs = db.query(AuditLog).filter_by(
            entity_type="property_assignment", entity_id=assignment_id,
        ).order_by(AuditLog.id).all()
        assert [entry.action for entry in revoked_logs] == ["created", "revoked"]
        assert json.loads(revoked_logs[1].old_value)["is_active"] is True
        assert json.loads(revoked_logs[1].new_value)["is_active"] is False
        assert remove_assignment(assignment_id, db=db, current_user=admin) is None
        assert db.query(AuditLog).filter_by(
            entity_type="property_assignment", entity_id=assignment_id,
        ).count() == 2

        revived = assign_user_to_property(
            second_property.id, crew.id, db=db, current_user=admin,
        )
        assert revived["assignment_id"] == assignment_id
        logs = db.query(AuditLog).filter_by(
            entity_type="property_assignment", entity_id=assignment_id,
        ).order_by(AuditLog.id).all()
        assert [entry.action for entry in logs] == ["created", "revoked", "reactivated"]
        assert json.loads(logs[-1].old_value)["is_active"] is False
        assert json.loads(logs[-1].new_value)["is_active"] is True

        assign_user_to_property(second_property.id, crew.id, db=db, current_user=admin)
        assert db.query(AuditLog).filter_by(
            entity_type="property_assignment", entity_id=assignment_id,
        ).count() == 3

        with pytest.raises(HTTPException) as denied:
            remove_assignment(assignment_id, db=db, current_user=foreign_admin)
        assert denied.value.status_code == 403
        assert db.query(AuditLog).filter_by(
            entity_type="property_assignment", entity_id=assignment_id,
        ).count() == 3
    finally:
        db.close()
        engine.dispose()
