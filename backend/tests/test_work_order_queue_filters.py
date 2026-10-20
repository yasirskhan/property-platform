"""Phase 5 bounded work-order queue filters never expand a user's visibility."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401 - import complete model registry
from app.core.database import Base
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import MaintenanceOnCallShift, WorkOrderTimeCorrection, WorkOrderTimeEntry, WorkOrder, WorkOrderStatus, WorkOrderCategory, WorkOrderPriority, WorkOrderUpdate
from app.routers.work_orders import (list_work_orders, work_order_queue_summary, emergency_work_order_triage, _user_can_access_work_order, get_work_order, start_work_order, complete_work_order, update_work_order, assign_work_order, accept_work_order_assignment, reject_work_order_assignment, recall_work_order_assignment, update_crew_eta, create_work_order_time_entry, list_work_order_time_entries, get_work_order_time_ledger, pending_crew_time_corrections, list_maintenance_preferred_vendors, replace_maintenance_preferred_vendors, list_maintenance_vendor_candidates, list_maintenance_on_call_shifts, schedule_maintenance_on_call_shift, cancel_maintenance_on_call_shift, request_work_order_time_correction, list_work_order_time_corrections, review_work_order_time_correction, submit_work_order, acknowledge_work_order, cancel_work_order, add_comment, requestable_work_order_units, possible_duplicate_work_orders)
from app.models.audit_log import AuditLog
from app.models.vendor import Vendor, MaintenancePreferredVendor
from app.models.vendor_insurance import VendorInsurance
from app.models.unit_inspection import UnitInspectionRecord
from app.services import unit_inspections
from app.routers.properties import check_property_access, visible_properties_query
from app.routers.users import assign_user_to_property, list_assignments, remove_assignment, update_user, deactivate_user
from app.models.lease import Lease, LeaseStatus
from app.schemas.work_order import MaintenanceOnCallShiftCreate, MaintenanceOnCallShiftCancel, MaintenanceVendorPreferencesUpdate, WorkOrderComplete, WorkOrderUpdateFields, WorkOrderAssign, WorkOrderReject, WorkOrderRecall, WorkOrderEta, WorkOrderTimeCreate, WorkOrderTimeCorrectionCreate, WorkOrderTimeCorrectionDecision, WorkOrderCreate, WorkOrderComment, WorkOrderCancel
from app.schemas.user import UserUpdate
from app.core import auth as auth_logic
from app.core.security import create_access_token, create_two_factor_challenge_token
from app.routers.auth import get_current_user, verify_two_factor_login
from app.schemas.two_factor import TwoFactorLoginVerifyRequest
from fastapi import HTTPException, Response
from app.routers import unit_inspections as inspection_router
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
        assignment_response=filters.get("assignment_response"),
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


def test_staff_origin_never_grants_tenant_visibility_even_with_tenant_id():
    db, engine, actors, _properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        row = orders[0]
        assert row.tenant_id == tenant.id
        # Historical unknown origin keeps existing tenant visibility.
        assert row.request_origin is None
        assert _user_can_access_work_order(db, tenant, row)
        row.request_origin = "staff"
        row.requested_by_user_id = admin.id
        db.commit()
        # Even deliberately malformed legacy tenant_id cannot turn an
        # authenticated staff request into a tenant-owned record.
        assert not _user_can_access_work_order(db, tenant, row)
        assert all(item.id != row.id for item in _queue(db, tenant))
        row.priority = WorkOrderPriority.EMERGENCY
        db.commit()
        assert row.id not in [item.id for item in emergency_work_order_triage(db=db, current_user=tenant)]
        assert row.id not in [item.id for item in possible_duplicate_work_orders(
            unit_id=row.unit_id, title="100% water", db=db, current_user=tenant,
        )]
        with pytest.raises(HTTPException) as denied:
            get_work_order(row.id, db=db, current_user=tenant)
        assert denied.value.status_code == 403
        assert _user_can_access_work_order(db, admin, row)
        row.request_origin = "tenant"
        row.requested_by_user_id = admin.id
        db.commit()
        assert not _user_can_access_work_order(db, tenant, row)
        assert all(item.id != row.id for item in _queue(db, tenant))
        row.requested_by_user_id = tenant.id
        db.commit()
        assert _user_can_access_work_order(db, tenant, row)
        assert any(item.id == row.id for item in _queue(db, tenant))
        assert not _user_can_access_work_order(db, foreign_admin, row)
    finally:
        db.close()
        engine.dispose()


def test_inspection_linked_work_order_validates_real_scoped_source(monkeypatch):
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        own, hidden, foreign_prop = properties
        evidence = UnitInspectionRecord(
            organization_id=admin.organization_id,
            property_id=orders[0].property_id, unit_id=orders[0].unit_id,
            inspection_date=date.today(), recorded_condition="ATTENTION_NEEDED",
            findings="Electrical panel needs investigation", recorded_by_id=admin.id,
        )
        foreign_evidence = UnitInspectionRecord(
            organization_id=foreign_admin.organization_id,
            property_id=orders[3].property_id, unit_id=orders[3].unit_id,
            inspection_date=date.today(), recorded_condition="ATTENTION_NEEDED",
            findings="Foreign inspection", recorded_by_id=foreign_admin.id,
        )
        wrong_unit = db.query(Unit).filter(Unit.property_id == hidden.id).one()
        other_evidence = UnitInspectionRecord(
            organization_id=admin.organization_id,
            property_id=hidden.id, unit_id=wrong_unit.id,
            inspection_date=date.today(), recorded_condition="ATTENTION_NEEDED",
            findings="Different unit inspection", recorded_by_id=admin.id,
        )
        db.add_all([evidence, foreign_evidence, other_evidence])
        db.flush()
        def request(source_id, actor=admin):
            return submit_work_order(
                WorkOrderCreate(
                    unit_id=orders[0].unit_id, title="Inspection follow-up",
                    description="Follow up on recorded inspection evidence.",
                    source_inspection_id=source_id,
                ), db=db, current_user=actor,
            )
        created = request(evidence.id)
        manager_created = request(evidence.id, manager)
        assert manager_created.source_inspection_id == evidence.id
        assert manager_created.requested_by_user_id == manager.id
        assert created.source_inspection_id == evidence.id
        def followups(actor):
            return inspection_router.get_inspection_work_orders(
                evidence.id, Response(), db=db, current_user=actor,
            )
        assert [row.id for row in followups(admin)] == [manager_created.id, created.id]
        assert [row.id for row in followups(manager)] == [manager_created.id, created.id]
        for unauthorized in (tenant, foreign_admin):
            with pytest.raises(HTTPException) as forbidden:
                followups(unauthorized)
            assert forbidden.value.status_code in {403, 404}
        audit = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=created.id, action="status_transition",
        ).one()
        assert json.loads(audit.new_value)["source_inspection_id"] == evidence.id
        assert get_work_order(created.id, db=db, current_user=admin).source_inspection_id == evidence.id
        assert get_work_order(created.id, db=db, current_user=manager).source_inspection_id == evidence.id
        created.assigned_to_id = crew.id
        db.commit()
        # Assigned crew may inspect the work order but not the private source
        # inspection record, even though its ID is stored internally.
        assert get_work_order(created.id, db=db, current_user=crew).source_inspection_id is None
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: False)
        assert get_work_order(created.id, db=db, current_user=manager).source_inspection_id is None
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        for source_id in (other_evidence.id, foreign_evidence.id, evidence.id + 99999):
            with pytest.raises(HTTPException) as exc:
                request(source_id)
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as denied:
            request(evidence.id, tenant)
        assert denied.value.status_code == 403
        assert db.query(WorkOrder).filter_by(source_inspection_id=evidence.id).count() == 2
        # Even a corrupted work-order unit cannot be presented as a follow-up.
        other_unit = db.query(Unit).filter(Unit.property_id == hidden.id).one()
        manager_created.unit_id = other_unit.id
        db.commit()
        assert [row.id for row in followups(admin)] == [created.id]
    finally:
        db.close()
        engine.dispose()


def test_staff_submissions_do_not_invent_tenant_or_grant_tenant_read_access():
    """Lock down existing behavior before separating requester from tenant."""
    db, engine, actors, _properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        created = submit_work_order(
            WorkOrderCreate(
                unit_id=orders[0].unit_id,
                title="Preventive equipment review",
                description="Staff records a property maintenance concern.",
            ),
            db=db, current_user=admin,
        )
        # A staff request is not assigned a fictional tenant. Historical
        # records retain their original value without unsafe backfill.
        assert created.tenant_id is None
        assert created.request_origin == "staff"
        assert created.requested_by_user_id == admin.id
        persisted = db.query(WorkOrder).filter_by(id=created.id).one()
        assert persisted.request_origin == "staff"
        assert persisted.requested_by_user_id == admin.id
        history = db.query(WorkOrderUpdate).filter_by(work_order_id=created.id).all()
        assert len(history) == 1
        assert history[0].user_id == admin.id
        created_audit = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=created.id, action="status_transition",
        ).one()
        assert created_audit.user_id == admin.id
        detail = get_work_order(created.id, db=db, current_user=admin)
        assert detail.request_origin == "staff"
        assert detail.requested_by_user_id == admin.id
        assert json.loads(created_audit.new_value) == {
            "status": WorkOrderStatus.SUBMITTED.value,
            "request_origin": "staff",
            "requested_by_user_id": admin.id,
        }
        assert _user_can_access_work_order(db, admin, created)
        assert not _user_can_access_work_order(db, tenant, created)
        assert not _user_can_access_work_order(db, other_tenant, created)
        assert not _user_can_access_work_order(db, foreign_admin, created)
        assert all(row.id != created.id for row in _queue(db, tenant))
        assert all(row.id != created.id for row in _queue(db, other_tenant))
        assert any(row.id == created.id for row in _queue(db, admin))
    finally:
        db.close()
        engine.dispose()


def test_work_order_detail_legacy_provenance_fails_closed():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, _manager, _tenant, _other, _crew, outside_admin = actors
        detail = get_work_order(orders[0].id, db=db, current_user=admin)
        assert orders[0].request_origin is None
        assert orders[0].requested_by_user_id is None
        assert detail.request_origin == "unknown_legacy"
        assert detail.requested_by_user_id is None
        with pytest.raises(HTTPException) as denied:
            get_work_order(orders[0].id, db=db, current_user=outside_admin)
        assert denied.value.status_code == 403
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
            "pending_crew_response": 0, "declined_assignment": 0, "recalled_assignment": 0,
            "in_progress": 1, "ready_to_close": 0,
        }
        manager_counts = work_order_queue_summary(db=db, current_user=manager)
        assert manager_counts == {
            "open": 2, "emergency_open": 0, "awaiting_assignment": 1,
            "pending_crew_response": 0, "declined_assignment": 0, "recalled_assignment": 0,
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


def test_staff_offboarding_user_active_state_is_audited_and_idempotent():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        assert crew.is_active is True
        assert deactivate_user(crew.id, db=db, current_user=admin) is None
        assert crew.is_active is False
        logs = db.query(AuditLog).filter_by(
            entity_type="user", entity_id=crew.id,
        ).order_by(AuditLog.id).all()
        assert [row.action for row in logs] == ["deactivated"]
        assert logs[0].user_id == admin.id
        assert logs[0].organization_id == admin.organization_id
        assert json.loads(logs[0].old_value) == {"is_active": True}
        assert json.loads(logs[0].new_value) == {"is_active": False}
        deactivate_user(crew.id, db=db, current_user=admin)
        assert db.query(AuditLog).filter_by(
            entity_type="user", entity_id=crew.id,
        ).count() == 1

        updated = update_user(
            crew.id, UserUpdate(is_active=True), db=db, current_user=admin,
        )
        assert updated.is_active is True
        logs = db.query(AuditLog).filter_by(
            entity_type="user", entity_id=crew.id,
        ).order_by(AuditLog.id).all()
        assert [row.action for row in logs] == ["deactivated", "activated"]
        assert json.loads(logs[-1].old_value) == {"is_active": False}
        assert json.loads(logs[-1].new_value) == {"is_active": True}

        with pytest.raises(HTTPException) as invalid:
            update_user(crew.id, UserUpdate(is_active=None), db=db, current_user=admin)
        assert invalid.value.status_code == 400
        assert crew.is_active is True

        with pytest.raises(HTTPException) as foreign:
            deactivate_user(crew.id, db=db, current_user=foreign_admin)
        assert foreign.value.status_code == 403
        assert db.query(AuditLog).filter_by(
            entity_type="user", entity_id=crew.id,
        ).count() == 2

        # A soft-deleted account needs its own controlled restoration flow.
        crew.is_active = False
        crew.deleted_at = datetime(2026, 10, 18, 12)
        db.commit()
        with pytest.raises(HTTPException) as deleted_restore:
            update_user(crew.id, UserUpdate(is_active=True), db=db, current_user=admin)
        assert deleted_restore.value.status_code == 409
        assert crew.is_active is False
        assert db.query(AuditLog).filter_by(
            entity_type="user", entity_id=crew.id,
        ).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_deactivated_or_deleted_customer_cannot_authenticate_reuse_jwt_or_finish_mfa(monkeypatch):
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        # Auth logic is tested independently of a costly bcrypt roundtrip.
        monkeypatch.setattr(auth_logic, "verify_password", lambda _p, _hash: True)
        access_token = create_access_token(subject=crew.id)
        challenge_token = create_two_factor_challenge_token(subject=crew.id)
        assert auth_logic.authenticate_user(db, crew.email, "supplied-password").id == crew.id
        assert get_current_user(token=access_token, db=db).id == crew.id

        crew.is_active = False
        db.commit()
        assert auth_logic.authenticate_user(db, crew.email, "supplied-password") is None
        with pytest.raises(HTTPException) as jwt_denied:
            get_current_user(token=access_token, db=db)
        assert jwt_denied.value.status_code == 401
        with pytest.raises(HTTPException) as mfa_denied:
            verify_two_factor_login(
                TwoFactorLoginVerifyRequest(challenge_token=challenge_token, code="123456"),
                request=None, db=db,
            )
        assert mfa_denied.value.status_code == 401

        # Even inconsistent historical records marked active remain revoked.
        crew.is_active = True
        crew.deleted_at = datetime(2026, 10, 18, 12)
        db.commit()
        assert auth_logic.authenticate_user(db, crew.email, "supplied-password") is None
        with pytest.raises(HTTPException) as deleted_jwt:
            get_current_user(token=access_token, db=db)
        assert deleted_jwt.value.status_code == 401
        with pytest.raises(HTTPException) as deleted_mfa:
            verify_two_factor_login(
                TwoFactorLoginVerifyRequest(challenge_token=challenge_token, code="123456"),
                request=None, db=db,
            )
        assert deleted_mfa.value.status_code == 401
    finally:
        db.close()
        engine.dispose()


def test_malformed_customer_jwt_or_two_factor_subject_is_unauthorized_not_server_error():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        malformed = create_access_token(subject="not-a-user-number")
        with pytest.raises(HTTPException) as jwt_invalid:
            get_current_user(token=malformed, db=db)
        assert jwt_invalid.value.status_code == 401

        challenge = create_two_factor_challenge_token(subject="not-a-user-number")
        with pytest.raises(HTTPException) as mfa_invalid:
            verify_two_factor_login(
                TwoFactorLoginVerifyRequest(challenge_token=challenge, code="123456"),
                request=None, db=db,
            )
        assert mfa_invalid.value.status_code == 401
    finally:
        db.close()
        engine.dispose()


def test_work_order_detail_location_labels_respect_existing_scope():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, external_admin = actors
        own_order = orders[0]
        detail = get_work_order(own_order.id, db=db, current_user=admin)
        assert detail.id == own_order.id
        assert detail.property_name == "Assigned Property"
        assert detail.unit_number == "A1"
        assert isinstance(detail.updates, list)

        # Labels cannot be requested by a caller denied work-order detail.
        with pytest.raises(HTTPException) as denied:
            get_work_order(own_order.id, db=db, current_user=external_admin)
        assert denied.value.status_code == 403
        with pytest.raises(HTTPException) as tenant_denied:
            get_work_order(own_order.id, db=db, current_user=other_tenant)
        assert tenant_denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_explicit_work_order_cancel_is_audited_and_terminal():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        own_order = orders[0]
        assert own_order.status == WorkOrderStatus.SUBMITTED
        with pytest.raises(HTTPException) as forbidden:
            cancel_work_order(own_order.id, db=db, current_user=tenant)
        assert forbidden.value.status_code == 403
        assert own_order.status == WorkOrderStatus.SUBMITTED

        with pytest.raises(HTTPException) as blank:
            cancel_work_order(own_order.id, payload=WorkOrderCancel(reason="     "), db=db, current_user=admin)
        assert blank.value.status_code == 422
        assert own_order.status == WorkOrderStatus.SUBMITTED

        cancelled = cancel_work_order(
            own_order.id,
            payload=WorkOrderCancel(reason="Duplicate of another maintenance request"),
            db=db, current_user=admin,
        )
        assert cancelled.status == WorkOrderStatus.CANCELLED
        assert db.query(WorkOrderUpdate).filter_by(
            work_order_id=own_order.id, to_status=WorkOrderStatus.CANCELLED,
        ).count() == 1
        audit = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=own_order.id,
            action="status_transition",
        ).order_by(AuditLog.id.desc()).first()
        assert audit is not None and audit.user_id == admin.id
        assert json.loads(audit.new_value) == {
            "status": "cancelled", "reason": "Duplicate of another maintenance request",
        }
        assert db.query(WorkOrderUpdate).filter_by(
            work_order_id=own_order.id,
            message="Cancelled: Duplicate of another maintenance request",
        ).count() == 1

        with pytest.raises(HTTPException) as finished:
            cancel_work_order(own_order.id, db=db, current_user=admin)
        assert finished.value.status_code == 400
        assert db.query(WorkOrderUpdate).filter_by(
            work_order_id=own_order.id, to_status=WorkOrderStatus.CANCELLED,
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_work_order_activity_actor_names_are_scoped_to_property_organization():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        wo = orders[0]
        add_comment(wo.id, WorkOrderComment(message="Actual local comment"), db=db, current_user=admin)
        foreign_row = WorkOrderUpdate(
            work_order_id=wo.id, user_id=foreign_admin.id,
            message="Historical cross-org actor ID deliberately malformed",
        )
        db.add(foreign_row)
        db.commit()
        detail = get_work_order(wo.id, db=db, current_user=admin)
        local = next(x for x in detail.updates if x.message == "Actual local comment")
        outside = next(x for x in detail.updates if x.id == foreign_row.id)
        assert local.actor_name == "QueueAdmin Tester"
        assert outside.actor_name is None
        with pytest.raises(HTTPException) as denied:
            get_work_order(wo.id, db=db, current_user=foreign_admin)
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_work_order_queue_returns_scoped_location_labels_without_expanding_visibility():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        p1, p2, p3 = properties
        rows = _queue(db, admin, limit=2)
        assert len(rows) == 2
        # Same timestamp queue ordering uses descending ID: second property first.
        assert [(row.property_name, row.unit_number) for row in rows] == [
            ("Other Property", "A1"), ("Assigned Property", "A1"),
        ]
        assert [row.property_id for row in rows] == [p2.id, p1.id]
        restricted = _queue(db, manager, limit=50)
        assert {row.property_id for row in restricted} == {p1.id}
        assert all(row.property_name == "Assigned Property" for row in restricted)
        assert _queue(db, foreign_admin, property_id=p1.id) == []
        assert all(row.property_name == "External Property" for row in _queue(db, foreign_admin))
        assert all(row.property_name == "Other Property" for row in _queue(db, other_tenant))
    finally:
        db.close()
        engine.dispose()


def test_work_order_activity_note_rejects_whitespace_without_audit_or_mutation():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin = actors[0]
        order = orders[0]
        before_updates = db.query(WorkOrderUpdate).filter_by(work_order_id=order.id).count()
        before_audit = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id, action="comment_added",
        ).count()
        with pytest.raises(HTTPException) as rejected:
            add_comment(order.id, WorkOrderComment(message=" \n \t "), db=db, current_user=admin)
        assert rejected.value.status_code == 422
        assert db.query(WorkOrderUpdate).filter_by(work_order_id=order.id).count() == before_updates
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id, action="comment_added",
        ).count() == before_audit

        saved = add_comment(
            order.id, WorkOrderComment(message="  Inspected kitchen sink.  "),
            db=db, current_user=admin,
        )
        assert saved.message == "Inspected kitchen sink."
        assert saved.actor_name == "QueueAdmin Tester"
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id, action="comment_added",
        ).count() == before_audit + 1
    finally:
        db.close()
        engine.dispose()


def test_work_order_queue_search_matches_scoped_property_and_unit_text():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outside_admin = actors
        a, b, c, d = orders
        assert [row.id for row in _queue(db, admin, search="Assigned Property")] == [b.id, a.id]
        assert [row.id for row in _queue(db, manager, search="Assigned Property")] == [b.id, a.id]
        assert _queue(db, manager, search="Other Property") == []
        assert [row.id for row in _queue(db, other_tenant, search="Other Property")] == [c.id]
        assert _queue(db, outside_admin, search="Assigned Property") == []
        assert [row.id for row in _queue(db, outside_admin, search="External Property")] == [d.id]
        assert [row.id for row in _queue(db, crew, search="A1")] == [a.id]
        assert [row.id for row in _queue(db, admin, search="A1")] == [c.id, b.id, a.id]
        assert _queue(db, admin, search="A_") == []
    finally:
        db.close()
        engine.dispose()


def test_emergency_triage_is_bounded_oldest_first_and_role_scoped():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        a, b, c, d = orders

        def triage(user):
            return emergency_work_order_triage(db=db, current_user=user)

        assert [row.id for row in triage(admin)] == [c.id]
        assert [row.id for row in triage(other_tenant)] == [c.id]
        assert [row.id for row in triage(foreign_admin)] == [d.id]
        assert triage(manager) == []
        assert triage(crew) == []
        assert triage(tenant) == []

        a.priority = WorkOrderPriority.EMERGENCY
        a.status = WorkOrderStatus.ACKNOWLEDGED
        a.created_at = datetime(2026, 10, 17, 12)
        db.commit()
        # Submitted requests are triaged first even if acknowledged older.
        assert [row.id for row in triage(admin)] == [c.id, a.id]
        assert [row.id for row in triage(manager)] == [a.id]
        assert [row.id for row in triage(tenant)] == [a.id]
        assert [row.id for row in triage(crew)] == [a.id]
        assert [(row.property_name, row.unit_number) for row in triage(admin)] == [
            ("Other Property", "A1"), ("Assigned Property", "A1"),
        ]

        # Historical active flags must never override a revoked property
        # assignment when selecting emergencies for staff.
        for staff in (manager, crew):
            assignment = db.query(PropertyAssignment).filter_by(
                property_id=a.property_id, user_id=staff.id,
            ).one()
            assignment.is_active = True
            assignment.deleted_at = datetime(2026, 10, 18, 13)
        db.commit()
        assert triage(manager) == []
        assert triage(crew) == []
        assert [row.id for row in triage(admin)] == [c.id, a.id]

        c.status = WorkOrderStatus.CANCELLED
        d.status = WorkOrderStatus.CLOSED
        db.commit()
        assert [row.id for row in triage(admin)] == [a.id]
        assert triage(other_tenant) == []
        assert triage(foreign_admin) == []

        for i in range(30):
            row = WorkOrder(
                property_id=a.property_id, unit_id=a.unit_id, tenant_id=tenant.id,
                title=f"Emergency test {i}", description="Authorized seeded issue",
                priority=WorkOrderPriority.EMERGENCY, category=WorkOrderCategory.GENERAL,
                status=WorkOrderStatus.SUBMITTED,
                created_at=datetime(2026, 10, 18, 12, 0),
            )
            db.add(row)
        db.commit()
        assert len(triage(admin)) == 20
        assert all(row.priority == WorkOrderPriority.EMERGENCY for row in triage(admin))
        assert a.id not in [row.id for row in triage(admin)]
    finally:
        db.close()
        engine.dispose()


def test_assigned_crew_must_accept_before_start_and_duplicate_acceptance_is_noop():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        assigned = assign_work_order(
            row.id, WorkOrderAssign(crew_user_id=crew.id), db=db, current_user=manager,
        )
        assert assigned.assignment_response == "pending"
        assert assigned.assignment_responded_at is None
        with pytest.raises(HTTPException) as premature:
            start_work_order(row.id, db=db, current_user=crew)
        assert premature.value.status_code == 409
        accepted = accept_work_order_assignment(row.id, db=db, current_user=crew)
        assert accepted.assignment_response == "accepted"
        assert accepted.assignment_responded_at is not None
        accept_work_order_assignment(row.id, db=db, current_user=crew)
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id,
            action="crew_assignment_accepted",
        ).count() == 1
        assert start_work_order(row.id, db=db, current_user=crew).status == WorkOrderStatus.IN_PROGRESS
        with pytest.raises(HTTPException):
            reject_work_order_assignment(
                row.id, WorkOrderReject(reason="Cannot attend this shift"),
                db=db, current_user=crew,
            )
        assert db.query(WorkOrder).filter_by(id=row.id).one().assigned_to_id == crew.id
    finally:
        db.close()
        engine.dispose()


def test_crew_rejection_unassigns_atomically_preserves_reason_and_allows_reassignment():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=admin)
        with pytest.raises(HTTPException) as blank:
            reject_work_order_assignment(
                row.id, WorkOrderReject(reason="     "),
                db=db, current_user=crew,
            )
        assert blank.value.status_code == 422
        rejected = reject_work_order_assignment(
            row.id, WorkOrderReject(reason="Unavailable during overnight shift"),
            db=db, current_user=crew,
        )
        assert rejected.status == WorkOrderStatus.ACKNOWLEDGED
        assert rejected.assigned_to_id is None
        assert rejected.assignment_response == "rejected"
        assert rejected.assigned_at is None and rejected.assigned_by_id is None
        assert not _user_can_access_work_order(db, crew, row)
        with pytest.raises(HTTPException) as denied:
            reject_work_order_assignment(
                row.id, WorkOrderReject(reason="Repeated rejection attempt"),
                db=db, current_user=crew,
            )
        assert denied.value.status_code == 403
        event = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id,
            action="crew_assignment_rejected",
        ).one()
        assert json.loads(event.new_value)["reason"] == "Unavailable during overnight shift"
        reassigned = assign_work_order(
            row.id, WorkOrderAssign(crew_user_id=crew.id), db=db, current_user=manager,
        )
        assert reassigned.assignment_response == "pending"
        assert reassigned.assignment_responded_at is None
        assert reassigned.status == WorkOrderStatus.ASSIGNED
        assert db.query(WorkOrderUpdate).filter_by(work_order_id=row.id).count() >= 3
    finally:
        db.close()
        engine.dispose()


def test_crew_dispatch_decisions_deny_revoked_assignments_foreign_org_and_legacy_forgery():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ASSIGNED
        row.assignment_response = "pending"
        db.commit()
        for actor in (tenant, manager, outsider):
            with pytest.raises(HTTPException) as forbidden:
                accept_work_order_assignment(row.id, db=db, current_user=actor)
            assert forbidden.value.status_code == 403
        foreign = orders[3]
        foreign.status = WorkOrderStatus.ASSIGNED
        foreign.assignment_response = "pending"
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            accept_work_order_assignment(foreign.id, db=db, current_user=crew)
        assert blocked.value.status_code == 403
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=properties[0].id, user_id=crew.id,
        ).one()
        assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as revoked:
            accept_work_order_assignment(row.id, db=db, current_user=crew)
        assert revoked.value.status_code == 403
        assignment.is_active = True
        db.commit()
        row.assignment_response = None
        db.commit()
        # A corrupt row marked assigned after rejection must never bypass acceptance.
        row.assignment_response = "rejected"
        db.commit()
        with pytest.raises(HTTPException) as forged_start:
            start_work_order(row.id, db=db, current_user=crew)
        assert forged_start.value.status_code == 409
        row.assignment_response = None
        db.commit()
        # Historical work orders have no acceptance flag and remain startable.
        with pytest.raises(HTTPException) as no_fake_ack:
            accept_work_order_assignment(row.id, db=db, current_user=crew)
        assert no_fake_ack.value.status_code == 409
        assert start_work_order(row.id, db=db, current_user=crew).status == WorkOrderStatus.IN_PROGRESS
    finally:
        db.close()
        engine.dispose()


def test_dispatch_attention_filters_sort_priority_and_respect_role_scope():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, outsider = actors
        a, b, c, foreign = orders
        a.status = WorkOrderStatus.ASSIGNED
        a.assignment_response = "pending"
        a.assigned_to_id = crew.id
        a.priority = WorkOrderPriority.HIGH
        b.status = WorkOrderStatus.ACKNOWLEDGED
        b.assignment_response = "rejected"
        b.assigned_to_id = None
        c.status = WorkOrderStatus.ASSIGNED
        c.assignment_response = "pending"
        c.priority = WorkOrderPriority.EMERGENCY
        foreign.status = WorkOrderStatus.ASSIGNED
        foreign.assignment_response = "pending"
        db.commit()
        assert [row.id for row in _queue(db, admin, assignment_response="pending")] == [
            c.id, a.id,
        ]
        assert [row.id for row in _queue(db, manager, assignment_response="pending")] == [a.id]
        assert [row.id for row in _queue(db, crew, assignment_response="pending")] == [a.id]
        assert [row.id for row in _queue(db, tenant, assignment_response="pending")] == [a.id]
        assert [row.id for row in _queue(db, admin, assignment_response="rejected")] == [b.id]
        assert [row.id for row in _queue(db, manager, assignment_response="rejected")] == [b.id]
        assert _queue(db, crew, assignment_response="rejected") == []
        assert [row.id for row in _queue(db, outsider, assignment_response="pending")] == [foreign.id]
        summary = work_order_queue_summary(db=db, current_user=manager)
        assert summary["pending_crew_response"] == 1
        assert summary["declined_assignment"] == 1
        assert work_order_queue_summary(db=db, current_user=crew)["pending_crew_response"] == 1
        assert work_order_queue_summary(db=db, current_user=crew)["declined_assignment"] == 0
    finally:
        db.close()
        engine.dispose()


def test_new_dispatch_refuses_retired_property_or_unit_without_audit_or_assignment():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign_admin = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        prop = properties[0]
        unit = db.get(Unit, row.unit_id)
        for change in ("property_inactive", "unit_inactive", "property_deleted", "unit_deleted"):
            prop.is_active, prop.deleted_at = True, None
            unit.is_active, unit.deleted_at = True, None
            if change == "property_inactive":
                prop.is_active = False
            elif change == "unit_inactive":
                unit.is_active = False
            elif change == "property_deleted":
                prop.deleted_at = datetime.utcnow()
            else:
                unit.deleted_at = datetime.utcnow()
            db.commit()
            with pytest.raises(HTTPException) as denied:
                assign_work_order(
                    row.id, WorkOrderAssign(crew_user_id=crew.id), db=db, current_user=admin,
                )
            assert denied.value.status_code == 409
            assert row.assigned_to_id is None
            assert row.status == WorkOrderStatus.ACKNOWLEDGED
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id,
            action="crew_assignment",
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_staff_recall_unstarted_crew_offer_records_distinct_audit_and_restores_queue():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=admin)
        for nonstaff in (tenant, crew, outsider):
            with pytest.raises(HTTPException) as forbidden:
                recall_work_order_assignment(row.id, WorkOrderRecall(reason="Dispatch no longer required"),
                                             db=db, current_user=nonstaff)
            assert forbidden.value.status_code == 403
        with pytest.raises(HTTPException) as empty_reason:
            recall_work_order_assignment(row.id, WorkOrderRecall(reason="     "),
                                         db=db, current_user=manager)
        assert empty_reason.value.status_code == 422
        assert row.assignment_response == "pending"
        recalled = recall_work_order_assignment(
            row.id, WorkOrderRecall(reason="Move crew to a higher priority repair"),
            db=db, current_user=manager,
        )
        assert recalled.status == WorkOrderStatus.ACKNOWLEDGED
        assert recalled.assigned_to_id is None and recalled.assigned_by_id is None
        assert recalled.assignment_response == "recalled"
        assert recalled.assignment_responded_at is not None
        assert work_order_queue_summary(db=db, current_user=manager)["recalled_assignment"] == 1
        assert [result.id for result in _queue(db, manager, assignment_response="recalled")] == [row.id]
        with pytest.raises(HTTPException) as stale_crew:
            accept_work_order_assignment(row.id, db=db, current_user=crew)
        assert stale_crew.value.status_code == 403
        with pytest.raises(HTTPException) as repeated:
            recall_work_order_assignment(row.id, WorkOrderRecall(reason="Repeated staff recall"),
                                         db=db, current_user=manager)
        assert repeated.value.status_code == 409
        events = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id,
            action="crew_assignment_recalled",
        ).all()
        assert len(events) == 1
        assert json.loads(events[0].new_value)["reason"] == "Move crew to a higher priority repair"
        assert json.loads(events[0].old_value)["assigned_to_id"] == crew.id
        assigned = assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                                     db=db, current_user=manager)
        assert assigned.assignment_response == "pending"
    finally:
        db.close()
        engine.dispose()


def test_staff_recall_deny_started_and_revoked_manager_scope():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, _tenant, _other, crew, _outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ASSIGNED
        row.assignment_response = "accepted"
        db.commit()
        manager_assignment = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=manager.id,
        ).one()
        manager_assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as revoked:
            recall_work_order_assignment(row.id, WorkOrderRecall(reason="Manager is no longer assigned"),
                                         db=db, current_user=manager)
        assert revoked.value.status_code == 403
        row.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        with pytest.raises(HTTPException) as started:
            recall_work_order_assignment(row.id, WorkOrderRecall(reason="Attempted after start"),
                                         db=db, current_user=admin)
        assert started.value.status_code == 409
        assert row.assigned_to_id == crew.id
        assert db.query(AuditLog).filter_by(entity_type="work_order", entity_id=row.id,
                                            action="crew_assignment_recalled").count() == 0
    finally:
        db.close()
        engine.dispose()


def test_dispatch_accept_and_start_recheck_active_property_unit_after_offer():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, _manager, _tenant, _other, crew, _foreign = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=admin)
        prop = properties[0]
        unit = db.get(Unit, row.unit_id)
        for state in ("property_inactive", "unit_inactive", "property_deleted", "unit_deleted"):
            prop.is_active, prop.deleted_at = True, None
            unit.is_active, unit.deleted_at = True, None
            if state == "property_inactive":
                prop.is_active = False
            elif state == "unit_inactive":
                unit.is_active = False
            elif state == "property_deleted":
                prop.deleted_at = datetime.utcnow()
            else:
                unit.deleted_at = datetime.utcnow()
            db.commit()
            with pytest.raises(HTTPException) as blocked:
                accept_work_order_assignment(row.id, db=db, current_user=crew)
            assert blocked.value.status_code == 409
            assert row.assignment_response == "pending"
        prop.is_active, prop.deleted_at = True, None
        unit.is_active, unit.deleted_at = True, None
        db.commit()
        accepted = accept_work_order_assignment(row.id, db=db, current_user=crew)
        assert accepted.assignment_response == "accepted"
        prop.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as blocked_start:
            start_work_order(row.id, db=db, current_user=crew)
        assert blocked_start.value.status_code == 409
        assert row.status == WorkOrderStatus.ASSIGNED
        prop.is_active = True
        db.commit()
        assert start_work_order(row.id, db=db, current_user=crew).status == WorkOrderStatus.IN_PROGRESS
        assert db.query(AuditLog).filter_by(entity_type="work_order", entity_id=row.id,
                                            action="crew_assignment_accepted").count() == 1
    finally:
        db.close()
        engine.dispose()


def test_only_accepted_current_crew_can_set_future_audited_arrival_eta():
    db, engine, actors, _properties, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=manager)
        eta = datetime.now(timezone.utc) + timedelta(hours=12)
        with pytest.raises(HTTPException) as pending:
            update_crew_eta(row.id, WorkOrderEta(eta_at=eta), db=db, current_user=crew)
        assert pending.value.status_code == 409
        accept_work_order_assignment(row.id, db=db, current_user=crew)
        for bad_actor in (admin, manager, tenant, outsider):
            with pytest.raises(HTTPException) as blocked:
                update_crew_eta(row.id, WorkOrderEta(eta_at=eta), db=db, current_user=bad_actor)
            assert blocked.value.status_code == 403
        for invalid in (datetime.utcnow(), datetime.now(timezone.utc) - timedelta(days=1),
                        datetime.now(timezone.utc) + timedelta(days=31)):
            with pytest.raises(HTTPException) as blocked:
                update_crew_eta(row.id, WorkOrderEta(eta_at=invalid), db=db, current_user=crew)
            assert blocked.value.status_code == 422
        recorded = update_crew_eta(row.id, WorkOrderEta(eta_at=eta), db=db, current_user=crew)
        assert recorded.crew_eta_at == eta.astimezone(timezone.utc).replace(tzinfo=None)
        update_crew_eta(row.id, WorkOrderEta(eta_at=eta), db=db, current_user=crew)
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id, action="crew_eta_updated",
        ).count() == 1
        assert start_work_order(row.id, db=db, current_user=crew).status == WorkOrderStatus.IN_PROGRESS
        with pytest.raises(HTTPException):
            update_crew_eta(row.id, WorkOrderEta(eta_at=eta + timedelta(hours=1)),
                            db=db, current_user=crew)
        assert row.crew_eta_at is not None
    finally:
        db.close()
        engine.dispose()


def test_staff_recall_clears_eta_with_previously_promised_time_in_audit():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, manager, _tenant, _other, crew, _outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.ACKNOWLEDGED
        row.assigned_to_id = None
        db.commit()
        assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                          db=db, current_user=admin)
        accept_work_order_assignment(row.id, db=db, current_user=crew)
        estimate = datetime.now(timezone.utc) + timedelta(hours=8)
        update_crew_eta(row.id, WorkOrderEta(eta_at=estimate), db=db, current_user=crew)
        previous = estimate.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
        recalled = recall_work_order_assignment(
            row.id, WorkOrderRecall(reason="Urgent crew reallocation"),
            db=db, current_user=manager,
        )
        assert recalled.crew_eta_at is None
        audit = db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id, action="crew_assignment_recalled",
        ).one()
        assert json.loads(audit.old_value)["crew_eta_at"] == previous
        assert json.loads(audit.new_value)["crew_eta_at"] is None
        restarted = assign_work_order(row.id, WorkOrderAssign(crew_user_id=crew.id),
                                      db=db, current_user=manager)
        assert restarted.crew_eta_at is None
        assert restarted.assignment_response == "pending"
    finally:
        db.close()
        engine.dispose()


def test_crew_time_entries_are_authorized_nonoverlapping_and_audited():
    db, engine, actors, _props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = actors
        row = orders[0]
        row.status = WorkOrderStatus.IN_PROGRESS
        row.assigned_to_id = crew.id
        db.commit()
        start = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(second=0, microsecond=0)
        end = start + timedelta(hours=1)
        payload = WorkOrderTimeCreate(started_at=start, ended_at=end, notes="Replaced faulty part")
        for actor in (admin, manager, tenant, outsider):
            with pytest.raises(HTTPException) as unauthorized:
                create_work_order_time_entry(row.id, payload, db=db, current_user=actor)
            assert unauthorized.value.status_code == 403
        logged = create_work_order_time_entry(row.id, payload, db=db, current_user=crew)
        assert logged.duration_minutes == 60
        replay = create_work_order_time_entry(row.id, payload, db=db, current_user=crew)
        assert replay.id == logged.id
        assert len(list_work_order_time_entries(row.id, db=db, current_user=manager)) == 1
        with pytest.raises(HTTPException) as private:
            list_work_order_time_entries(row.id, db=db, current_user=tenant)
        assert private.value.status_code == 403
        with pytest.raises(HTTPException) as collision:
            create_work_order_time_entry(row.id, WorkOrderTimeCreate(
                started_at=start + timedelta(minutes=30), ended_at=end + timedelta(minutes=30),
            ), db=db, current_user=crew)
        assert collision.value.status_code == 409
        with pytest.raises(HTTPException) as future:
            create_work_order_time_entry(row.id, WorkOrderTimeCreate(
                started_at=start + timedelta(days=2), ended_at=end + timedelta(days=2),
            ), db=db, current_user=crew)
        assert future.value.status_code == 422
        assert db.query(WorkOrderTimeEntry).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=row.id, action="crew_time_recorded",
        ).count() == 1
        row.status = WorkOrderStatus.COMPLETED
        db.commit()
        with pytest.raises(HTTPException) as closed:
            create_work_order_time_entry(row.id, WorkOrderTimeCreate(
                started_at=end, ended_at=end + timedelta(minutes=30),
            ), db=db, current_user=crew)
        assert closed.value.status_code == 409
    finally:
        db.close()
        engine.dispose()


def test_crew_time_correction_two_person_scope_replay_and_immutable_original():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _, crew, foreign = actors
        wo = orders[0]
        wo.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        start = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(second=0, microsecond=0)
        original = create_work_order_time_entry(wo.id, WorkOrderTimeCreate(
            started_at=start, ended_at=start + timedelta(hours=1)), db=db, current_user=crew)
        proposal = WorkOrderTimeCorrectionCreate(
            started_at=start, ended_at=start + timedelta(minutes=90),
            reason="Original interval ended too soon")
        for actor in (admin, manager, tenant, foreign):
            with pytest.raises(HTTPException):
                request_work_order_time_correction(wo.id, original.id, proposal, db=db, current_user=actor)
        req = request_work_order_time_correction(wo.id, original.id, proposal, db=db, current_user=crew)
        assert req.status == "pending"
        assert request_work_order_time_correction(wo.id, original.id, proposal, db=db, current_user=crew).id == req.id
        for actor in (crew, tenant, foreign):
            with pytest.raises(HTTPException):
                review_work_order_time_correction(wo.id, req.id,
                    WorkOrderTimeCorrectionDecision(approve=True, reason="Verified repair duration"),
                    db=db, current_user=actor)
        assert len(list_work_order_time_corrections(wo.id, db=db, current_user=manager)) == 1
        with pytest.raises(HTTPException):
            list_work_order_time_corrections(wo.id, db=db, current_user=tenant)
        approved = review_work_order_time_correction(wo.id, req.id,
            WorkOrderTimeCorrectionDecision(approve=True, reason="Verified repair duration"),
            db=db, current_user=manager)
        assert approved.status == "approved"
        assert db.get(WorkOrderTimeEntry, original.id).duration_minutes == 60
        assert db.query(AuditLog).filter_by(entity_type="work_order", entity_id=wo.id,
                                            action="crew_time_correction_requested").count() == 1
        assert db.query(AuditLog).filter_by(entity_type="work_order", entity_id=wo.id,
                                            action="crew_time_correction_reviewed").count() == 1
        with pytest.raises(HTTPException) as repeat:
            review_work_order_time_correction(wo.id, req.id,
                WorkOrderTimeCorrectionDecision(approve=False, reason="Repeat review"), db=db, current_user=admin)
        assert repeat.value.status_code == 409
    finally:
        db.close(); engine.dispose()


def test_crew_time_correction_conflict_denial_and_revoked_manager():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, _, _, crew, foreign = actors
        wo = orders[0]
        wo.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        start = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(second=0, microsecond=0)
        first = create_work_order_time_entry(wo.id, WorkOrderTimeCreate(
            started_at=start, ended_at=start + timedelta(hours=1)), db=db, current_user=crew)
        create_work_order_time_entry(wo.id, WorkOrderTimeCreate(
            started_at=start + timedelta(hours=2), ended_at=start + timedelta(hours=3)),
            db=db, current_user=crew)
        req = request_work_order_time_correction(wo.id, first.id, WorkOrderTimeCorrectionCreate(
            started_at=start, ended_at=start + timedelta(minutes=150),
            reason="Repair took more time"), db=db, current_user=crew)
        with pytest.raises(HTTPException) as conflict:
            review_work_order_time_correction(wo.id, req.id,
                WorkOrderTimeCorrectionDecision(approve=True, reason="Verify against second entry"),
                db=db, current_user=admin)
        assert conflict.value.status_code == 409
        assignment = db.query(PropertyAssignment).filter_by(property_id=props[0].id, user_id=manager.id).one()
        assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            review_work_order_time_correction(wo.id, req.id,
                WorkOrderTimeCorrectionDecision(approve=False, reason="Correction overlaps"),
                db=db, current_user=manager)
        assert blocked.value.status_code == 403
        denied = review_work_order_time_correction(wo.id, req.id,
            WorkOrderTimeCorrectionDecision(approve=False, reason="Conflicts with other time record"),
            db=db, current_user=admin)
        assert denied.status == "denied"
    finally:
        db.close(); engine.dispose()


def test_time_summary_retains_original_minutes_after_separate_review():
    db, engine, actors, _, orders = _seed_queue()
    try:
        admin, manager, tenant, _, crew, foreign = actors
        wo = orders[0]
        wo.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        start = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(second=0, microsecond=0)
        original = create_work_order_time_entry(wo.id, WorkOrderTimeCreate(
            started_at=start, ended_at=start + timedelta(hours=1)),
            db=db, current_user=crew)
        raw = get_work_order_time_ledger(wo.id, db=db, current_user=admin)
        assert (raw.recorded_entries, raw.recorded_minutes, raw.reviewed_minutes) == (1, 60, 60)
        correction = request_work_order_time_correction(
            wo.id, original.id, WorkOrderTimeCorrectionCreate(
                started_at=start, ended_at=start + timedelta(minutes=90),
                reason="Actual repair included further cleanup"),
            db=db, current_user=crew)
        assert get_work_order_time_ledger(
            wo.id, db=db, current_user=manager).pending_corrections == 1
        review_work_order_time_correction(
            wo.id, correction.id, WorkOrderTimeCorrectionDecision(
                approve=True, reason="Manager verified completion time"),
            db=db, current_user=manager)
        ledger = get_work_order_time_ledger(wo.id, db=db, current_user=crew)
        assert (ledger.recorded_minutes, ledger.reviewed_minutes) == (60, 90)
        assert (ledger.approved_entries, ledger.pending_corrections) == (1, 0)
        assert ledger.payroll_approved is False
        assert db.get(WorkOrderTimeEntry, original.id).duration_minutes == 60
        for actor in (tenant, foreign):
            with pytest.raises(HTTPException) as denied:
                get_work_order_time_ledger(wo.id, db=db, current_user=actor)
            assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_time_summary_is_empty_without_original_evidence():
    db, engine, actors, _, orders = _seed_queue()
    try:
        admin, _, tenant, _, _, _ = actors
        empty = get_work_order_time_ledger(orders[0].id, db=db, current_user=admin)
        assert empty.recorded_entries == 0
        assert empty.reviewed_minutes == 0
        with pytest.raises(HTTPException):
            get_work_order_time_ledger(orders[0].id, db=db, current_user=tenant)
    finally:
        db.close()
        engine.dispose()


def test_pending_time_review_inbox_scopes_property_org_staff_and_decisions():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _, crew, outsider = actors
        first, _, off_property, foreign = orders
        first.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        start = (datetime.now(timezone.utc) - timedelta(hours=4)).replace(second=0, microsecond=0)
        original = create_work_order_time_entry(
            first.id, WorkOrderTimeCreate(
                started_at=start, ended_at=start + timedelta(hours=1)),
            db=db, current_user=crew)
        pending = request_work_order_time_correction(
            first.id, original.id, WorkOrderTimeCorrectionCreate(
                started_at=start, ended_at=start + timedelta(minutes=75),
                reason="Rechecked actual repair time"), db=db, current_user=crew)
        # Same org but a property not assigned to this manager.
        for hidden in (off_property, foreign):
            evidence = WorkOrderTimeEntry(
                work_order_id=hidden.id, crew_user_id=crew.id,
                started_at=start, ended_at=start + timedelta(minutes=30),
                duration_minutes=30,
            )
            db.add(evidence)
            db.flush()
            db.add(WorkOrderTimeCorrection(
                work_order_id=hidden.id, time_entry_id=evidence.id,
                requested_by_user_id=crew.id,
                proposed_started_at=start,
                proposed_ended_at=start + timedelta(minutes=45),
                duration_minutes=45, reason="Should remain scoped", status="pending",
            ))
        db.commit()
        admin_rows = pending_crew_time_corrections(limit=50, offset=0, db=db, current_user=admin)
        assert {r.work_order_id for r in admin_rows} == {first.id, off_property.id}
        assert [r.work_order_id for r in pending_crew_time_corrections(
            limit=10, offset=0, db=db, current_user=manager)] == [first.id]
        assert pending_crew_time_corrections(limit=1, offset=0, db=db, current_user=admin)
        assert len(pending_crew_time_corrections(limit=1, offset=1, db=db, current_user=admin)) == 1
        for actor in (tenant, crew):
            with pytest.raises(HTTPException) as denied:
                pending_crew_time_corrections(limit=10, offset=0, db=db, current_user=actor)
            assert denied.value.status_code == 403
        review_work_order_time_correction(first.id, pending.id,
            WorkOrderTimeCorrectionDecision(approve=True, reason="Time checked with technician"),
            db=db, current_user=manager)
        assert pending_crew_time_corrections(limit=10, offset=0, db=db, current_user=manager) == []
        manager_assignment = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=manager.id).one()
        manager_assignment.is_active = False
        db.commit()
        assert pending_crew_time_corrections(limit=10, offset=0, db=db, current_user=manager) == []
    finally:
        db.close()
        engine.dispose()


def test_crew_time_requester_cannot_approve_after_role_change():
    db, engine, actors, _, orders = _seed_queue()
    try:
        admin, manager, _, _, crew, _ = actors
        wo = orders[0]
        wo.status = WorkOrderStatus.IN_PROGRESS
        db.commit()
        start = (datetime.now(timezone.utc) - timedelta(hours=4)).replace(second=0, microsecond=0)
        evidence = create_work_order_time_entry(wo.id, WorkOrderTimeCreate(
            started_at=start, ended_at=start + timedelta(minutes=60)),
            db=db, current_user=crew)
        correction = request_work_order_time_correction(
            wo.id, evidence.id, WorkOrderTimeCorrectionCreate(
                started_at=start, ended_at=start + timedelta(minutes=80),
                reason="Additional installation activity"), db=db, current_user=crew)
        crew.role = UserRole.MANAGER
        db.commit()
        with pytest.raises(HTTPException) as denied:
            review_work_order_time_correction(
                wo.id, correction.id, WorkOrderTimeCorrectionDecision(
                    approve=True, reason="Attempt to self approve"),
                db=db, current_user=crew)
        assert denied.value.status_code == 403
        assert db.get(WorkOrderTimeCorrection, correction.id).status == "pending"
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=wo.id,
            action="crew_time_correction_reviewed",
        ).count() == 0
        assert review_work_order_time_correction(
            wo.id, correction.id, WorkOrderTimeCorrectionDecision(
                approve=True, reason="Independent property manager verified"),
            db=db, current_user=manager).status == "approved"
    finally:
        db.close()
        engine.dispose()



def test_ranked_property_trade_vendor_preferences_scoped_and_audited():
    db, engine, actors, properties, orders = _seed_queue()
    try:
        admin, manager, tenant, _, crew, foreign = actors
        prop = properties[0]
        order = orders[0]
        org_id = admin.organization_id
        def vendor(name, trade, org=org_id):
            row = Vendor(organization_id=org, company_name=name, trade=trade,
                         is_active=True, created_by_id=admin.id)
            db.add(row)
            db.flush()
            return row
        plumber_a = vendor("City Plumbing", "plumbing")
        plumber_b = vendor("Blue Water", "plumbing")
        electrician = vendor("Electrical Corp", "electrical")
        general = vendor("All Trades", None)
        outsider_vendor = vendor("Foreign Supplier", "plumbing", foreign.organization_id)
        db.add_all([
            VendorInsurance(organization_id=org_id, vendor_id=plumber_a.id,
                            carrier="Test Carrier", coverage_type="general liability",
                            expiration_date=date.today() + timedelta(days=80), is_active=True),
            VendorInsurance(organization_id=org_id, vendor_id=plumber_b.id,
                            carrier="Old Carrier", coverage_type="general liability",
                            expiration_date=date.today() - timedelta(days=1), is_active=True),
        ])
        db.commit()
        assert list_maintenance_preferred_vendors(order.id, db=db, current_user=admin) == []
        eligible_ids = {v.vendor_id for v in list_maintenance_vendor_candidates(order.id, db=db, current_user=manager)}
        assert eligible_ids == {plumber_a.id, plumber_b.id, general.id}
        insurance = {v.vendor_id: v.insurance_status for v in list_maintenance_vendor_candidates(
            order.id, db=db, current_user=manager)}
        assert insurance[plumber_a.id] == "CURRENT"
        assert insurance[plumber_b.id] == "EXPIRED"
        assert insurance[general.id] == "MISSING"
        plumber_a.trade = " PLUMBING "
        db.commit()
        assert plumber_a.id in {v.vendor_id for v in list_maintenance_vendor_candidates(
            order.id, db=db, current_user=manager)}
        for actor in (tenant, crew, foreign):
            with pytest.raises(HTTPException):
                list_maintenance_preferred_vendors(order.id, db=db, current_user=actor)
            with pytest.raises(HTTPException):
                replace_maintenance_preferred_vendors(
                    order.id, MaintenanceVendorPreferencesUpdate(vendor_ids=[plumber_a.id]),
                    db=db, current_user=actor)
        for candidate in ([plumber_a.id, plumber_a.id],
                          [plumber_a.id, plumber_b.id, general.id, electrician.id]):
            # Duplicates are rejected by the route; overly long payload by Pydantic.
            if len(candidate) > 3:
                with pytest.raises(Exception):
                    MaintenanceVendorPreferencesUpdate(vendor_ids=candidate)
            else:
                with pytest.raises(HTTPException) as invalid:
                    replace_maintenance_preferred_vendors(order.id,
                        MaintenanceVendorPreferencesUpdate(vendor_ids=candidate),
                        db=db, current_user=admin)
                assert invalid.value.status_code == 422
        for not_eligible in (electrician.id, outsider_vendor.id):
            with pytest.raises(HTTPException) as denied:
                replace_maintenance_preferred_vendors(order.id,
                    MaintenanceVendorPreferencesUpdate(vendor_ids=[not_eligible]),
                    db=db, current_user=admin)
            assert denied.value.status_code == 404
        expected = [plumber_b.id, plumber_a.id, general.id]
        saved = replace_maintenance_preferred_vendors(order.id,
            MaintenanceVendorPreferencesUpdate(vendor_ids=expected),
            db=db, current_user=manager)
        assert [v.vendor_id for v in saved] == expected
        assert [v.rank for v in saved] == [1, 2, 3]
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_vendor_preferences", entity_id=prop.id,
            action="ranked_vendor_preferences_updated").count() == 1
        again = replace_maintenance_preferred_vendors(order.id,
            MaintenanceVendorPreferencesUpdate(vendor_ids=expected),
            db=db, current_user=manager)
        assert [v.vendor_id for v in again] == expected
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_vendor_preferences", entity_id=prop.id,
            action="ranked_vendor_preferences_updated").count() == 1
        assert list_maintenance_preferred_vendors(orders[2].id, db=db, current_user=admin) == []
        assert list_maintenance_preferred_vendors(orders[1].id, db=db, current_user=manager) == []
        plumber_b.is_active = False
        db.commit()
        assert [v.vendor_id for v in list_maintenance_preferred_vendors(order.id, db=db, current_user=admin)] == [plumber_a.id, general.id]
        result = replace_maintenance_preferred_vendors(order.id,
            MaintenanceVendorPreferencesUpdate(vendor_ids=[]),
            db=db, current_user=admin)
        assert result == []
        assert db.query(MaintenancePreferredVendor).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_preferred_vendor_settings_fail_closed_when_property_retired_or_manager_revoked():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, other, crew, outsider = actors
        order = orders[0]
        vendor = Vendor(organization_id=admin.organization_id,
                        company_name="Local HVAC", trade=None, is_active=True)
        db.add(vendor)
        db.commit()
        unit = db.get(Unit, order.unit_id)
        for location in ("inactive_property", "inactive_unit", "deleted_property", "deleted_unit"):
            prop = props[0]
            prop.is_active, prop.deleted_at = True, None
            unit.is_active, unit.deleted_at = True, None
            if location == "inactive_property":
                prop.is_active = False
            elif location == "inactive_unit":
                unit.is_active = False
            elif location == "deleted_property":
                prop.deleted_at = datetime.utcnow()
            else:
                unit.deleted_at = datetime.utcnow()
            db.commit()
            with pytest.raises(HTTPException) as blocked:
                replace_maintenance_preferred_vendors(order.id,
                    MaintenanceVendorPreferencesUpdate(vendor_ids=[vendor.id]),
                    db=db, current_user=admin)
            assert blocked.value.status_code == 409
        prop.is_active, prop.deleted_at = True, None
        unit.is_active, unit.deleted_at = True, None
        db.commit()
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=prop.id, user_id=manager.id).one()
        assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as revoked:
            replace_maintenance_preferred_vendors(order.id,
                MaintenanceVendorPreferencesUpdate(vendor_ids=[vendor.id]),
                db=db, current_user=manager)
        assert revoked.value.status_code == 403
        assert db.query(MaintenancePreferredVendor).count() == 0
    finally:
        db.close()
        engine.dispose()



def test_preferred_vendor_ranks_are_shared_by_property_and_trade_not_work_order():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _, crew, foreign = actors
        original = orders[0]
        sibling = WorkOrder(
            property_id=original.property_id, unit_id=original.unit_id,
            tenant_id=tenant.id, title="Another plumbing repair",
            description="Same property and trade shares dispatch preferences",
            category=WorkOrderCategory.PLUMBING, priority=WorkOrderPriority.MEDIUM,
            status=WorkOrderStatus.SUBMITTED,
        )
        general = orders[1]
        db.add(sibling)
        first = Vendor(organization_id=admin.organization_id, company_name="Best Pipe", trade="plumbing", is_active=True)
        second = Vendor(organization_id=admin.organization_id, company_name="Water Help", trade="plumbing", is_active=True)
        db.add_all([first, second])
        db.commit()
        replace_maintenance_preferred_vendors(original.id,
            MaintenanceVendorPreferencesUpdate(vendor_ids=[first.id, second.id]),
            db=db, current_user=admin)
        assert [r.vendor_id for r in list_maintenance_preferred_vendors(
            sibling.id, db=db, current_user=manager)] == [first.id, second.id]
        assert list_maintenance_preferred_vendors(general.id, db=db, current_user=admin) == []
        replace_maintenance_preferred_vendors(sibling.id,
            MaintenanceVendorPreferencesUpdate(vendor_ids=[second.id, first.id]),
            db=db, current_user=manager)
        assert [r.vendor_id for r in list_maintenance_preferred_vendors(
            original.id, db=db, current_user=admin)] == [second.id, first.id]
        audits = db.query(AuditLog).filter_by(
            entity_type="maintenance_vendor_preferences", entity_id=props[0].id,
            action="ranked_vendor_preferences_updated",
        ).order_by(AuditLog.id.asc()).all()
        assert len(audits) == 2
        assert json.loads(audits[-1].old_value)["vendor_ids"] == [first.id, second.id]
        assert json.loads(audits[-1].new_value)["vendor_ids"] == [second.id, first.id]
        assert db.query(MaintenancePreferredVendor).count() == 2
    finally:
        db.close()
        engine.dispose()



def test_on_call_crew_schedule_conflicts_idempotency_and_scoped_cancellation():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _, crew, external_admin = actors
        start = (datetime.now(timezone.utc) + timedelta(days=3)).replace(second=0, microsecond=0)
        payload = MaintenanceOnCallShiftCreate(crew_user_id=crew.id,
                                                starts_at=start, ends_at=start + timedelta(hours=8))
        for actor in (tenant, crew, external_admin):
            with pytest.raises(HTTPException):
                schedule_maintenance_on_call_shift(orders[0].id, payload, db=db, current_user=actor)
        scheduled = schedule_maintenance_on_call_shift(orders[0].id, payload, db=db, current_user=manager)
        assert scheduled.crew_user_id == crew.id
        assert schedule_maintenance_on_call_shift(orders[0].id, payload, db=db, current_user=manager).id == scheduled.id
        with pytest.raises(HTTPException) as conflict:
            schedule_maintenance_on_call_shift(orders[0].id, MaintenanceOnCallShiftCreate(
                crew_user_id=crew.id, starts_at=start + timedelta(hours=1),
                ends_at=start + timedelta(hours=9)), db=db, current_user=admin)
        assert conflict.value.status_code == 409
        with pytest.raises(HTTPException) as invalid:
            schedule_maintenance_on_call_shift(orders[0].id, MaintenanceOnCallShiftCreate(
                crew_user_id=crew.id, starts_at=datetime.utcnow(),
                ends_at=datetime.utcnow() + timedelta(hours=3)), db=db, current_user=admin)
        assert invalid.value.status_code == 422
        assert [x.id for x in list_maintenance_on_call_shifts(
            orders[0].id, db=db, current_user=manager)] == [scheduled.id]
        for actor in (tenant, crew, external_admin):
            with pytest.raises(HTTPException):
                list_maintenance_on_call_shifts(orders[0].id, db=db, current_user=actor)
        with pytest.raises(HTTPException):
            cancel_maintenance_on_call_shift(orders[0].id, scheduled.id,
                MaintenanceOnCallShiftCancel(reason="Not permitted by tenant"), db=db, current_user=tenant)
        cancelled = cancel_maintenance_on_call_shift(orders[0].id, scheduled.id,
            MaintenanceOnCallShiftCancel(reason="Crew shifted to another property"),
            db=db, current_user=admin)
        assert cancelled.cancelled_at is not None
        assert cancel_maintenance_on_call_shift(orders[0].id, scheduled.id,
            MaintenanceOnCallShiftCancel(reason="Crew shifted to another property"),
            db=db, current_user=admin).id == scheduled.id
        with pytest.raises(HTTPException) as conflict:
            cancel_maintenance_on_call_shift(orders[0].id, scheduled.id,
                MaintenanceOnCallShiftCancel(reason="Different cancellation reason"),
                db=db, current_user=admin)
        assert conflict.value.status_code == 409
        assert db.query(MaintenanceOnCallShift).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_on_call_shift", entity_id=scheduled.id, action="scheduled").count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_on_call_shift", entity_id=scheduled.id, action="cancelled").count() == 1
        replacement = schedule_maintenance_on_call_shift(orders[0].id, payload, db=db, current_user=admin)
        assert replacement.id != scheduled.id
    finally:
        db.close()
        engine.dispose()


def test_on_call_crew_schedule_rejects_wrong_org_wrong_property_and_revocation():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, _, _, crew, foreign = actors
        start = (datetime.now(timezone.utc) + timedelta(days=5)).replace(second=0, microsecond=0)
        payload = MaintenanceOnCallShiftCreate(
            crew_user_id=crew.id, starts_at=start, ends_at=start + timedelta(hours=6))
        for work_order in (orders[2], orders[3]):
            with pytest.raises(HTTPException):
                schedule_maintenance_on_call_shift(work_order.id, payload,
                                                   db=db, current_user=manager)
        for crew_id in (foreign.id, 999998):
            with pytest.raises(HTTPException) as blocked:
                schedule_maintenance_on_call_shift(orders[0].id, MaintenanceOnCallShiftCreate(
                    crew_user_id=crew_id, starts_at=start, ends_at=start + timedelta(hours=6)),
                    db=db, current_user=admin)
            assert blocked.value.status_code == 404
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=crew.id).one()
        assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            schedule_maintenance_on_call_shift(orders[0].id, payload, db=db, current_user=admin)
        assert blocked.value.status_code == 404
        assignment.is_active = True
        manager_assignment = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=manager.id).one()
        manager_assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            schedule_maintenance_on_call_shift(orders[0].id, payload, db=db, current_user=manager)
        assert blocked.value.status_code == 403
        assert db.query(MaintenanceOnCallShift).count() == 0
    finally:
        db.close()
        engine.dispose()
