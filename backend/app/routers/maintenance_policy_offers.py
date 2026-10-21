"""Operator-confirmed policy-guided in-app crew offers.

This is an execution path for a configured primary CREW policy, not a
background scheduler or evidence of external notification. The existing
on-call assignment transaction remains the sole source of truth.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.routers.auth import get_current_user
from app.routers.work_orders import (
    _maintenance_vendor_scope, _check_access, _require_active_dispatch_location,
    _eligible_current_on_call, offer_current_on_call_crew,
)
from app.schemas.work_order import WorkOrderOut
from app.services.audit import append_audit_log
from app.services.maintenance_dispatch_policy import resolve_maintenance_dispatch_policy

router = APIRouter(prefix="/api/maintenance/policy-offers", tags=["Maintenance Policy Offers"])


@router.post("/work-orders/{work_order_id}", response_model=WorkOrderOut)
def offer_crew_using_policy(
    work_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revalidate staff, live location, rule and coverage before explicit offer.

    The property lock serializes crew schedule changes with the selected
    live shift; the work-order lock protects competing crew decisions.
    Audit evidence and assignment are committed by the existing assignment
    transaction, or neither persists when the operation fails.
    """
    work_order, prop = _maintenance_vendor_scope(
        db, work_order_id, current_user, write=True,
    )
    work_order = db.query(WorkOrder).filter(
        WorkOrder.id == work_order.id,
    ).with_for_update().one()
    _check_access(db, current_user, work_order)
    if work_order.status != WorkOrderStatus.ACKNOWLEDGED or work_order.assigned_to_id is not None:
        raise HTTPException(409, "An acknowledged, unassigned work order is required")
    _require_active_dispatch_location(db, work_order)
    policy = resolve_maintenance_dispatch_policy(
        db, prop=prop, priority=work_order.priority,
    )
    if not policy.configured or policy.first_target != "crew":
        raise HTTPException(409, "A configured primary on-call crew policy is required")
    eligible = _eligible_current_on_call(db, prop, datetime.utcnow())
    if eligible is None:
        raise HTTPException(409, "No eligible current on-call crew for the configured policy")
    shift, crew = eligible
    append_audit_log(
        db, user_id=current_user.id, organization_id=prop.organization_id,
        entity_type="work_order", entity_id=work_order.id,
        action="dispatch_policy_offer_authorized",
        old_value={"assigned_to_id": work_order.assigned_to_id},
        new_value={
            "source": "staff_confirmed_policy_offer",
            "group_id": policy.group_id,
            "urgency": policy.urgency,
            "daypart": policy.daypart,
            "first_target": policy.first_target,
            "backup_target": policy.backup_target,
            "timeout_minutes": policy.timeout_minutes,
            "escalation_setting": policy.escalate,
            "on_call_shift_id": shift.id,
            "crew_user_id": crew.id,
            "external_delivery_confirmed": False,
        },
    )
    # Existing routine rechecks coverage and records selection plus
    # pending crew offer in a single work-order assignment transaction.
    return offer_current_on_call_crew(
        work_order_id, db=db, current_user=current_user,
    )
