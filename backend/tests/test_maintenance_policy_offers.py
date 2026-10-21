"""Policy-bound crew offers: persisted in-app execution with no phantom delivery."""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.audit_log import AuditLog
from app.models.property import PropertyAssignment
from app.models.user import UserRole
from app.models.work_order import MaintenanceOnCallShift, WorkOrderStatus
from app.routers.maintenance_dispatch_groups import create_dispatch_group, save_dispatch_rule
from app.routers.maintenance_policy_offers import offer_crew_using_policy
from app.schemas.maintenance_dispatch import MaintenanceGroupInput, MaintenanceRuleInput
from test_work_order_queue_filters import _seed_queue


def _configuration(db, admin, prop, first_target):
    group = create_dispatch_group(
        MaintenanceGroupInput(
            name="Policy Crew Team", property_ids=[prop.id],
            timezone_name="America/New_York", business_start_hour=8,
            business_end_hour=18,
        ), db=db, current_user=admin,
    )
    for daypart in ("business_hours", "after_hours"):
        save_dispatch_rule(
            group.id, "low", daypart,
            MaintenanceRuleInput(
                first_target=first_target, backup_target="manager",
                timeout_minutes=12, escalate=True,
            ), db=db, current_user=admin,
        )
    return group


def test_operator_can_offer_only_after_policy_and_current_crew_are_both_verified():
    db, engine, people, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = people
        order = orders[1]  # LOW urgency -> low policy slot.
        order.status = WorkOrderStatus.ACKNOWLEDGED
        db.commit()

        def offer(actor=manager):
            return offer_crew_using_policy(order.id, db=db, current_user=actor)

        with pytest.raises(HTTPException) as missing:
            offer()
        assert missing.value.status_code == 409
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id,
            action="dispatch_policy_offer_authorized",
        ).count() == 0

        group = _configuration(db, admin, props[0], first_target="manager")
        with pytest.raises(HTTPException) as not_crew:
            offer()
        assert not_crew.value.status_code == 409

        for daypart in ("business_hours", "after_hours"):
            save_dispatch_rule(
                group.id, "low", daypart,
                MaintenanceRuleInput(
                    first_target="crew", backup_target="manager",
                    timeout_minutes=9, escalate=True,
                ), db=db, current_user=admin,
            )
        with pytest.raises(HTTPException) as not_on_call:
            offer()
        assert not_on_call.value.status_code == 409
        assert order.assigned_to_id is None

        now = datetime.utcnow()
        shift = MaintenanceOnCallShift(
            organization_id=admin.organization_id,
            property_id=props[0].id, crew_user_id=crew.id,
            starts_at=now - timedelta(minutes=5),
            ends_at=now + timedelta(minutes=40),
            created_by_user_id=admin.id,
        )
        db.add(shift)
        db.commit()
        for prohibited in (tenant, crew, outsider):
            with pytest.raises(HTTPException) as denied:
                offer(prohibited)
            assert denied.value.status_code in (403, 404)
        row = offer()
        assert row.status == WorkOrderStatus.ASSIGNED
        assert row.assigned_to_id == crew.id
        assert row.assignment_response == "pending"
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id,
            action="dispatch_policy_offer_authorized",
        ).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id,
            action="on_call_offer_selected",
        ).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id,
            action="crew_assignment",
        ).count() == 1
        with pytest.raises(HTTPException) as duplicate:
            offer()
        assert duplicate.value.status_code == 409
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id,
            action="dispatch_policy_offer_authorized",
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_policy_offer_fails_closed_after_manager_revocation_or_shift_cancellation():
    db, engine, people, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = people
        order = orders[1]
        order.status = WorkOrderStatus.ACKNOWLEDGED
        db.commit()
        _configuration(db, admin, props[0], first_target="crew")
        now = datetime.utcnow()
        shift = MaintenanceOnCallShift(
            organization_id=admin.organization_id, property_id=props[0].id,
            crew_user_id=crew.id, starts_at=now-timedelta(minutes=3),
            ends_at=now+timedelta(minutes=30), created_by_user_id=admin.id,
        )
        db.add(shift)
        db.commit()
        shift.cancelled_at = datetime.utcnow()
        db.commit()
        with pytest.raises(HTTPException) as cancelled:
            offer_crew_using_policy(order.id, db=db, current_user=admin)
        assert cancelled.value.status_code == 409

        shift.cancelled_at = None
        assignment = db.query(PropertyAssignment).filter_by(
            user_id=manager.id, property_id=props[0].id,
        ).one()
        assignment.role = UserRole.CREW
        db.commit()
        with pytest.raises(HTTPException) as revoked:
            offer_crew_using_policy(order.id, db=db, current_user=manager)
        assert revoked.value.status_code == 403
        assert order.assigned_to_id is None

        prop = props[0]
        prop.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as retired:
            offer_crew_using_policy(order.id, db=db, current_user=admin)
        assert retired.value.status_code == 409
        assert db.query(AuditLog).filter_by(
            entity_type="work_order", entity_id=order.id,
            action="dispatch_policy_offer_authorized",
        ).count() == 0
    finally:
        db.close()
        engine.dispose()
