"""Operator dispatch-attention inbox: scoping, urgency and manual timeout safety."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.property import PropertyAssignment
from app.models.user import UserRole
from app.models.work_order import WorkOrderStatus, WorkOrderPriority
from app.routers.maintenance_dispatch_attention import list_dispatch_attention
from app.routers.maintenance_dispatch_groups import create_dispatch_group, save_dispatch_rule
from app.schemas.maintenance_dispatch import MaintenanceGroupInput, MaintenanceRuleInput
from test_work_order_queue_filters import _seed_queue


def _entries(db, user, **kwargs):
    return list_dispatch_attention(db=db, current_user=user, **kwargs)


def test_attention_queue_orders_emergencies_and_prevents_foreign_or_tenant_visibility():
    db, engine, users, props, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign = users
        a, b, c, d = orders
        now = datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc)
        rows = _entries(db, admin, now_utc=now)
        assert [row.work_order_id for row in rows] == [c.id, a.id, b.id]
        assert rows[0].attention_code == "EMERGENCY_UNACKNOWLEDGED"
        assert all(row.policy_group is None and not row.policy_configured for row in rows)
        assert [row.work_order_id for row in _entries(db, manager, now_utc=now)] == [a.id, b.id]
        assert [row.work_order_id for row in _entries(db, foreign, now_utc=now)] == [d.id]
        for actor in (tenant, other_tenant, crew):
            with pytest.raises(HTTPException) as denied:
                _entries(db, actor)
            assert denied.value.status_code == 403
        assert [x.work_order_id for x in _entries(db, admin, offset=1, limit=1)] == [a.id]
        for param in ({"limit": 101}, {"limit": 0}, {"offset": -1}, {"offset": 10001}):
            with pytest.raises(HTTPException) as bad_page:
                _entries(db, admin, **param)
            assert bad_page.value.status_code == 422
    finally:
        db.close(); engine.dispose()


def test_attention_queue_flags_rejections_and_pending_policy_timeouts_without_mutation():
    db, engine, users, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, foreign = users
        a, b, c, d = orders
        now = datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc)
        a.status = WorkOrderStatus.ASSIGNED
        a.assignment_response = "pending"
        a.assigned_at = (now - timedelta(minutes=25)).replace(tzinfo=None)
        b.status = WorkOrderStatus.ACKNOWLEDGED
        b.assignment_response = "rejected"
        db.commit()
        group = create_dispatch_group(
            MaintenanceGroupInput(name="After hours team", property_ids=[props[0].id],
                                  timezone_name="America/New_York",
                                  business_start_hour=9, business_end_hour=17),
            db=db, current_user=admin,
        )
        rule = MaintenanceRuleInput(first_target="crew", backup_target="manager",
                                    timeout_minutes=10, escalate=True)
        for period in ("business_hours", "after_hours"):
            save_dispatch_rule(group.id, "normal", period, rule, db=db, current_user=admin)
        before = (a.assigned_to_id, a.assignment_response, a.status, a.assigned_at)
        rows = _entries(db, manager, now_utc=now)
        by_id = {row.work_order_id: row for row in rows}
        assert by_id[a.id].attention_code == "CREW_RESPONSE_OVERDUE"
        assert by_id[a.id].response_due_at == now - timedelta(minutes=15)
        assert by_id[a.id].policy_group == group.name
        assert by_id[a.id].primary_target == "crew"
        assert by_id[a.id].backup_target == "manager"
        assert by_id[b.id].attention_code == "REASSIGN_REQUIRED"
        assert b.assignment_response == "rejected"
        assert (a.assigned_to_id, a.assignment_response, a.status, a.assigned_at) == before
        a.assigned_at = (now - timedelta(minutes=5)).replace(tzinfo=None)
        db.commit()
        assert next(x for x in _entries(db, manager, now_utc=now)
                    if x.work_order_id == a.id).attention_code == "PENDING_CREW_RESPONSE"
        a.assignment_response = "accepted"
        db.commit()
        assert a.id not in [x.work_order_id for x in _entries(db, manager, now_utc=now)]
    finally:
        db.close(); engine.dispose()


def test_attention_queue_denies_revoked_and_mislabelled_manager_assignments():
    db, engine, users, props, orders = _seed_queue()
    try:
        admin, manager, tenant, other_tenant, crew, foreign = users
        target = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=manager.id
        ).one()
        target.role = UserRole.CREW
        db.commit()
        assert _entries(db, manager) == []
        target.role = UserRole.MANAGER
        target.is_active = False
        db.commit()
        assert _entries(db, manager) == []
        manager.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as denied:
            _entries(db, manager)
        assert denied.value.status_code == 403
    finally:
        db.close(); engine.dispose()


def test_attention_pagination_skips_resolved_assignments_before_limit_and_offset():
    """Resolved crew offers must not consume a dispatch inbox page slot."""
    db, engine, users, props, orders = _seed_queue()
    try:
        admin = users[0]
        first, second, third, _foreign = orders
        first.status = WorkOrderStatus.ASSIGNED
        first.assignment_response = "accepted"
        second.status = WorkOrderStatus.ACKNOWLEDGED
        third.status = WorkOrderStatus.SUBMITTED
        db.commit()
        # Although an accepted assignment has higher priority than the
        # acknowledged work order, the first page must contain live work.
        page = _entries(db, admin, limit=1, offset=0)
        assert [row.work_order_id for row in page] == [third.id]
        next_page = _entries(db, admin, limit=1, offset=1)
        assert [row.work_order_id for row in next_page] == [second.id]
        assert all(row.work_order_id != first.id for row in page + next_page)
    finally:
        db.close(); engine.dispose()
