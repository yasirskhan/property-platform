"""Safe, durable automated in-app attention for overdue policy crew offers."""
from datetime import datetime, timedelta, timezone

from app.models.audit_log import AuditLog
from app.models.maintenance_dispatch_auto_notice import MaintenanceDispatchAutoNotice
from app.models.work_order import WorkOrderStatus
from app.routers.maintenance_dispatch_groups import (
    create_dispatch_group, save_dispatch_rule, edit_dispatch_group,
)
from app.routers.maintenance_dispatch_attention import list_dispatch_attention
from app.schemas.maintenance_dispatch import MaintenanceGroupInput, MaintenanceRuleInput
from app.services.audit import append_audit_log
from app.services.maintenance_dispatch_auto_attention import sweep_due_auto_notices
from test_work_order_queue_filters import _seed_queue


def _policy(db, admin, prop, *, opt_in=True):
    group = create_dispatch_group(MaintenanceGroupInput(
        name="Escalation Policy", property_ids=[prop.id],
        timezone_name="America/New_York", business_start_hour=9,
        business_end_hour=17, automation_requested=opt_in,
    ), db=db, current_user=admin)
    for period in ("business_hours", "after_hours"):
        save_dispatch_rule(
            group.id, "normal", period,
            MaintenanceRuleInput(first_target="crew", backup_target="manager",
                                 timeout_minutes=1, escalate=True),
            db=db, current_user=admin,
        )
    return group


def _pending(db, admin, crew, order, group, now, *, verified=True):
    order.status = WorkOrderStatus.ASSIGNED
    order.assignment_response = "pending"
    order.assigned_to_id = crew.id
    order.assigned_at = (now - timedelta(seconds=90)).replace(tzinfo=None)
    db.commit()
    if verified:
        append_audit_log(
            db, entity_type="work_order", entity_id=order.id,
            organization_id=admin.organization_id, user_id=admin.id,
            action="dispatch_policy_offer_authorized",
            new_value={"source": "staff_confirmed_policy_offer",
                       "crew_user_id": crew.id, "group_id": group.id},
        )
        db.commit()


def test_automated_attention_requires_explicit_release_and_owner_intent_and_is_idempotent():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, _tenant, _other, crew, _foreign = actors
        now = datetime.now(timezone.utc)
        group = _policy(db, admin, props[0])
        order = orders[0]
        _pending(db, admin, crew, order, group, now)
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=False) == {
            "enabled": False, "created": 0, "checked": 0,
        }
        assert db.query(MaintenanceDispatchAutoNotice).count() == 0
        first = sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)
        assert first["enabled"] is True and first["created"] == 1
        notice = db.query(MaintenanceDispatchAutoNotice).one()
        assert notice.work_order_id == order.id
        assert notice.crew_user_id == crew.id
        assert notice.group_id == group.id
        assert notice.timeout_minutes == 1
        audit = db.query(AuditLog).filter_by(
            entity_type="maintenance_dispatch_auto_notice", entity_id=notice.id,
            action="system_attention_recorded",
        ).one()
        assert audit.user_id is None and audit.organization_id == admin.organization_id
        assert '"external_delivery_confirmed":false' in audit.new_value
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)["created"] == 0
        assert db.query(MaintenanceDispatchAutoNotice).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_dispatch_auto_notice", entity_id=notice.id,
            action="system_attention_recorded",
        ).count() == 1
        result = list_dispatch_attention(db=db, current_user=manager, now_utc=now)
        displayed = next(row for row in result if row.work_order_id == order.id)
        assert displayed.recorded_auto_notice_at is not None
        assert displayed.attention_code == "CREW_RESPONSE_OVERDUE"
        assert order.assignment_response == "pending"
        assert order.assigned_to_id == crew.id
        order.assignment_response = "accepted"
        db.commit()
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)["created"] == 0
    finally:
        db.close(); engine.dispose()


def test_automation_does_not_process_unapproved_group_or_nonpolicy_assignments():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, _tenant, _other, crew, _foreign = actors
        now = datetime.now(timezone.utc)
        group = _policy(db, admin, props[0], opt_in=False)
        order = orders[0]
        _pending(db, admin, crew, order, group, now)
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)["created"] == 0
        edit_dispatch_group(group.id, MaintenanceGroupInput(
            name="Escalation Policy", property_ids=[props[0].id],
            timezone_name="America/New_York", business_start_hour=9,
            business_end_hour=17, automation_requested=True,
        ), db=db, current_user=admin)
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)["created"] == 1
        # New manual pending offer must never be escalated using an earlier
        # policy-authorization audit for a different crew or offer window.
        second = orders[1]
        _pending(db, admin, crew, second, group, now, verified=False)
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)["created"] == 0
        assert db.query(MaintenanceDispatchAutoNotice).count() == 1
        # Revocation stops new automated records without altering the crew offer.
        crew.is_active = False
        db.commit()
        _pending(db, admin, crew, second, group, now, verified=True)
        assert sweep_due_auto_notices(db, now_utc=now, execution_enabled=True)["created"] == 0
        assert second.assigned_to_id == crew.id
    finally:
        db.close(); engine.dispose()
