"""Role-scoped, read-only maintenance dispatch attention queue.

This is an operator inbox, NOT an automatic caller, notification sender,
financial approval or self-executing dispatch engine. It never changes an
assignment. In particular, expired crew response windows do not silently
recall a real assignment.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderPriority
from app.routers.auth import get_current_user
from app.routers.work_orders import _visible_work_orders
from app.schemas.maintenance_dispatch_attention import MaintenanceDispatchAttentionOut
from app.services.maintenance_dispatch_policy import resolve_maintenance_dispatch_policy

router = APIRouter(prefix="/api/maintenance/dispatch-attention", tags=["Maintenance Dispatch Attention"])


def list_dispatch_attention(
    *,
    db: Session, current_user: User, limit: int = 50, offset: int = 0,
    now_utc: datetime | None = None,
) -> list[MaintenanceDispatchAttentionOut]:
    """A bounded, priority-ordered review queue with safe inheritance.

    Each entry reflects current stored state and a policy *preview*.
    Timeouts flag manual follow-up only; no notification is assumed delivered.
    """
    actor = current_user
    if (not actor.is_active or actor.deleted_at is not None
            or actor.organization_id is None
            or actor.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)):
        raise HTTPException(403, "Staff dispatch attention access required")
    org = db.query(Organization.id).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True),
        Organization.deleted_at.is_(None),
    ).first()
    if org is None:
        raise HTTPException(403, "Active organization required")
    if not (1 <= limit <= 100 and 0 <= offset <= 10000):
        raise HTTPException(422, "Dispatch attention page outside supported range")
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    queue = _visible_work_orders(db, actor).filter(
        WorkOrder.status.in_([
            WorkOrderStatus.SUBMITTED, WorkOrderStatus.ACKNOWLEDGED,
            WorkOrderStatus.ASSIGNED,
        ]),
        Property.is_active.is_(True), Property.deleted_at.is_(None),
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
    )
    # The legacy queue accepts *any* current property assignment for a
    # global MANAGER; here require the actual property assignment role.
    if actor.role == UserRole.MANAGER:
        queue = queue.filter(PropertyAssignment.role == UserRole.MANAGER)
    priority_order = case(
        (WorkOrder.priority == WorkOrderPriority.EMERGENCY, 0),
        (WorkOrder.priority == WorkOrderPriority.HIGH, 1),
        (WorkOrder.priority == WorkOrderPriority.MEDIUM, 2),
        else_=3,
    )
    records = (queue.order_by(priority_order, WorkOrder.created_at.asc(), WorkOrder.id.asc())
               .offset(offset).limit(limit).all())
    result: list[MaintenanceDispatchAttentionOut] = []
    for wo in records:
        # Revalidate the real Unit -> Property relationship rather than
        # trusting the work_order.property_id label.
        prop = db.query(Property).join(Unit, Unit.property_id == Property.id).filter(
            Unit.id == wo.unit_id,
            Property.id == wo.property_id,
            Property.organization_id == actor.organization_id,
        ).first()
        if prop is None:
            raise HTTPException(409, "Corrupt work-order dispatch location")
        policy = resolve_maintenance_dispatch_policy(
            db, prop=prop, priority=wo.priority, now_utc=now,
        )
        due = None
        if wo.status == WorkOrderStatus.SUBMITTED:
            code = "EMERGENCY_UNACKNOWLEDGED" if wo.priority == WorkOrderPriority.EMERGENCY else "UNACKNOWLEDGED"
            explanation = "Work order needs staff acknowledgement."
            action = "Open work order to review and acknowledge the request."
        elif wo.status == WorkOrderStatus.ACKNOWLEDGED:
            code = ("REASSIGN_REQUIRED" if wo.assignment_response in ("rejected", "recalled")
                    else "AWAITING_ASSIGNMENT")
            explanation = ("Crew offer rejected or recalled." if code == "REASSIGN_REQUIRED"
                           else "Acknowledged work order has no active assignment.")
            action = "Review on-call coverage and manually assign an eligible crew or vendor."
        elif wo.assignment_response == "pending":
            code = "PENDING_CREW_RESPONSE"
            explanation = "Crew has not responded to the in-app assignment."
            action = "Review the offered assignment; use explicit recall if reassignment is required."
            if policy.configured and policy.timeout_minutes is not None and wo.assigned_at is not None:
                start = wo.assigned_at
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                due = start + timedelta(minutes=policy.timeout_minutes)
                if now >= due:
                    code = "CREW_RESPONSE_OVERDUE"
                    explanation = "Configured response window elapsed without a crew decision."
                    action = "Manager must review the pending offer; no recall or escalation was executed."
        else:
            # Accepted/legacy crew assignments are not unresolved dispatch.
            continue
        result.append(MaintenanceDispatchAttentionOut(
            work_order_id=wo.id, property_id=prop.id, property_name=prop.name,
            title=wo.title, priority=wo.priority.value, status=wo.status.value,
            attention_code=code, explanation=explanation, next_action=action,
            assigned_to_id=wo.assigned_to_id, assignment_response=wo.assignment_response,
            response_due_at=due, policy_group=policy.group_name,
            policy_daypart=policy.daypart, policy_configured=policy.configured,
            primary_target=policy.first_target if policy.configured else None,
            backup_target=policy.backup_target if policy.configured else None,
        ))
    return result


@router.get("", response_model=list[MaintenanceDispatchAttentionOut])
def get_dispatch_attention(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_dispatch_attention(
        db=db, current_user=current_user, limit=limit, offset=offset,
    )
