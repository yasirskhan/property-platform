# ============================================================
# routers/work_orders.py
# ------------------------------------------------------------
# HTTP routes for the maintenance workflow:
#
#   POST   /work-orders                          tenant submits
#   GET    /work-orders                          list (role-scoped)
#   GET    /work-orders/{id}                     get one (with history)
#   PATCH  /work-orders/{id}                     manager edits
#   POST   /work-orders/{id}/acknowledge         manager sees it
#   POST   /work-orders/{id}/assign              manager assigns crew
#   POST   /work-orders/{id}/start               crew starts
#   POST   /work-orders/{id}/complete            crew completes
#   POST   /work-orders/{id}/close               manager approves & closes
#   POST   /work-orders/{id}/cancel              manager cancels
#   POST   /work-orders/{id}/comments            add a comment
#
# WHO SEES WHAT:
#   - Admin: all
#   - Owner: all in their org
#   - Manager: properties they're assigned to
#   - Crew: work orders assigned to them
#   - Tenant: their own work orders
# ============================================================

from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.models.work_order import (
    WorkOrder,
    WorkOrderUpdate,
    WorkOrderStatus,
)
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderDetail,
    WorkOrderUpdateFields,
    WorkOrderAssign,
    WorkOrderComplete,
    WorkOrderComment,
    WorkOrderUpdateOut,
)


router = APIRouter(prefix="/work-orders", tags=["Work Orders"])


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _require_role(current_user: User, *allowed: UserRole):
    if current_user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {[r.value for r in allowed]}",
        )


def _log_update(
    db: Session,
    wo: WorkOrder,
    user: User,
    from_status=None,
    to_status=None,
    message=None,
):
    """Append an entry to the work order's activity log."""
    entry = WorkOrderUpdate(
        work_order_id=wo.id,
        user_id=user.id,
        from_status=from_status,
        to_status=to_status,
        message=message,
    )
    db.add(entry)


def _get_property_for_work_order(db: Session, wo: WorkOrder) -> Property:
    unit = db.query(Unit).filter(Unit.id == wo.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    prop = db.query(Property).filter(Property.id == unit.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


def _user_can_access_work_order(db: Session, user: User, wo: WorkOrder) -> bool:
    """Returns True if the user is allowed to view this work order."""
    if user.role == UserRole.TENANT:
        return wo.tenant_id == user.id

    if user.role == UserRole.CREW:
        return wo.assigned_to_id == user.id

    if user.role in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        prop = _get_property_for_work_order(db, wo)

        if user.role in (UserRole.ADMIN, UserRole.OWNER):
            return prop.organization_id == user.organization_id

        # Manager: must be assigned to the property
        assigned = (
            db.query(PropertyAssignment)
            .filter(
                PropertyAssignment.property_id == prop.id,
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
            .first()
        )
        return bool(assigned)

    return False


def _check_access(db: Session, user: User, wo: WorkOrder) -> WorkOrder:
    if not _user_can_access_work_order(db, user, wo):
        raise HTTPException(status_code=403, detail="Access denied")
    return wo


def _visible_work_orders(db: Session, user: User):
    """Return a query pre-filtered to what this user can see."""
    q = db.query(WorkOrder)

    if user.role == UserRole.TENANT:
        return q.filter(WorkOrder.tenant_id == user.id)

    if user.role == UserRole.CREW:
        return q.filter(WorkOrder.assigned_to_id == user.id)

    if user.role in (UserRole.ADMIN, UserRole.OWNER):
        return (
            q.join(Property, Property.id == WorkOrder.property_id)
            .filter(Property.organization_id == user.organization_id)
        )

    if user.role == UserRole.MANAGER:
        return (
            q.join(PropertyAssignment, PropertyAssignment.property_id == WorkOrder.property_id)
            .filter(
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
        )

    return q.filter(WorkOrder.id == -1)


# ------------------------------------------------------------
# SUBMIT WORK ORDER
# ------------------------------------------------------------
@router.post("", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
def submit_work_order(
    payload: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a work order.
    - Tenants: for a unit they're leased to (checked against active lease).
    - Managers/Owners/Admins: for a unit in scope (e.g. reporting on behalf of tenant).
    """
    # Find the unit and property
    unit = db.query(Unit).filter(Unit.id == payload.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    prop = db.query(Property).filter(Property.id == unit.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Determine the tenant_id
    if current_user.role == UserRole.TENANT:
        # Confirm the tenant has an active lease on this unit
        from app.models.lease import Lease, LeaseStatus
        lease = (
            db.query(Lease)
            .filter(
                Lease.unit_id == unit.id,
                Lease.tenant_id == current_user.id,
                Lease.status == LeaseStatus.ACTIVE,
            )
            .first()
        )
        if not lease:
            raise HTTPException(status_code=403, detail="You are not an active tenant in this unit")
        tenant_id = current_user.id
    else:
        _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)
        check_property_access(db, current_user, prop.id)
        # Staff-originated work order: preserve existing submitter behavior.
        tenant_id = current_user.id

    wo = WorkOrder(
        unit_id=unit.id,
        property_id=prop.id,
        tenant_id=tenant_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        permission_to_enter=payload.permission_to_enter,
        entry_notes=payload.entry_notes,
        photo_urls=payload.photo_urls,
        status=WorkOrderStatus.SUBMITTED,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)

    _log_update(db, wo, current_user, to_status=WorkOrderStatus.SUBMITTED, message="Work order submitted")
    db.commit()
    db.refresh(wo)

    return wo


# ------------------------------------------------------------
# LIST WORK ORDERS
# ------------------------------------------------------------
@router.get("", response_model=List[WorkOrderOut])
def list_work_orders(
    status: WorkOrderStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _visible_work_orders(db, current_user)
    if status is not None:
        q = q.filter(WorkOrder.status == status)
    return q.order_by(WorkOrder.created_at.desc()).all()


# ------------------------------------------------------------
# GET ONE WORK ORDER (with history)
# ------------------------------------------------------------
@router.get("/{wo_id}", response_model=WorkOrderDetail)
def get_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)
    return wo


# ------------------------------------------------------------
# UPDATE FIELDS
# ------------------------------------------------------------
@router.patch("/{wo_id}", response_model=WorkOrderOut)
def update_work_order(
    wo_id: int,
    payload: WorkOrderUpdateFields,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(wo, field, value)

    db.commit()
    db.refresh(wo)

    if changes:
        _log_update(db, wo, current_user, message=f"Updated fields: {', '.join(changes.keys())}")
        db.commit()
        db.refresh(wo)

    return wo


# ------------------------------------------------------------
# ACKNOWLEDGE
# ------------------------------------------------------------
@router.post("/{wo_id}/acknowledge", response_model=WorkOrderOut)
def acknowledge_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)

    if wo.status != WorkOrderStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"Cannot acknowledge from status '{wo.status.value}'")

    old = wo.status
    wo.status = WorkOrderStatus.ACKNOWLEDGED
    db.commit()

    _log_update(db, wo, current_user, from_status=old, to_status=wo.status, message="Acknowledged")
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# ASSIGN TO CREW
# ------------------------------------------------------------
@router.post("/{wo_id}/assign", response_model=WorkOrderOut)
def assign_work_order(
    wo_id: int,
    payload: WorkOrderAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)

    # Verify the crew member exists, is crew, and is assigned to this property
    crew = db.query(User).filter(User.id == payload.crew_user_id).first()
    if not crew or crew.role != UserRole.CREW:
        raise HTTPException(status_code=400, detail="Invalid crew member")
    prop = _get_property_for_work_order(db, wo)
    if crew.organization_id != prop.organization_id:
        raise HTTPException(status_code=403, detail="Crew member is not in this organization")

    assigned = (
        db.query(PropertyAssignment)
        .filter(
            PropertyAssignment.property_id == wo.property_id,
            PropertyAssignment.user_id == crew.id,
            PropertyAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not assigned:
        raise HTTPException(status_code=400, detail="Crew member is not assigned to this property")

    old = wo.status
    wo.assigned_to_id = crew.id
    wo.assigned_at = datetime.utcnow()
    wo.assigned_by_id = current_user.id
    wo.status = WorkOrderStatus.ASSIGNED

    _log_update(
        db, wo, current_user,
        from_status=old, to_status=wo.status,
        message=f"Assigned to {crew.first_name} {crew.last_name}",
    )
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# START WORK
# ------------------------------------------------------------
@router.post("/{wo_id}/start", response_model=WorkOrderOut)
def start_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    # Only the assigned crew member can start
    if current_user.role != UserRole.CREW or wo.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned crew member can start work")

    if wo.status != WorkOrderStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail=f"Cannot start from status '{wo.status.value}'")

    old = wo.status
    wo.status = WorkOrderStatus.IN_PROGRESS

    _log_update(db, wo, current_user, from_status=old, to_status=wo.status, message="Work started")
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# COMPLETE (crew marks done)
# ------------------------------------------------------------
@router.post("/{wo_id}/complete", response_model=WorkOrderOut)
def complete_work_order(
    wo_id: int,
    payload: WorkOrderComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    if current_user.role != UserRole.CREW or wo.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned crew member can complete work")

    if wo.status != WorkOrderStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail=f"Cannot complete from status '{wo.status.value}'")

    old = wo.status
    wo.status = WorkOrderStatus.COMPLETED
    wo.completed_at = datetime.utcnow()

    if payload.resolution_notes is not None:
        wo.resolution_notes = payload.resolution_notes
    if payload.labor_cost is not None:
        wo.labor_cost = payload.labor_cost
    if payload.materials_cost is not None:
        wo.materials_cost = payload.materials_cost

    total = Decimal("0.00")
    if wo.labor_cost:
        total += wo.labor_cost
    if wo.materials_cost:
        total += wo.materials_cost
    wo.total_cost = total

    _log_update(db, wo, current_user, from_status=old, to_status=wo.status, message="Work completed")
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# CLOSE (manager approves)
# ------------------------------------------------------------
@router.post("/{wo_id}/close", response_model=WorkOrderOut)
def close_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)

    if wo.status != WorkOrderStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Cannot close from status '{wo.status.value}'")

    old = wo.status
    wo.status = WorkOrderStatus.CLOSED
    wo.closed_at = datetime.utcnow()

    _log_update(db, wo, current_user, from_status=old, to_status=wo.status, message="Closed by manager")
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# CANCEL
# ------------------------------------------------------------
@router.post("/{wo_id}/cancel", response_model=WorkOrderOut)
def cancel_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)

    if wo.status in (WorkOrderStatus.CLOSED, WorkOrderStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Work order is already finished")

    old = wo.status
    wo.status = WorkOrderStatus.CANCELLED

    _log_update(db, wo, current_user, from_status=old, to_status=wo.status, message="Cancelled")
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# ADD COMMENT
# ------------------------------------------------------------
@router.post("/{wo_id}/comments", response_model=WorkOrderUpdateOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    wo_id: int,
    payload: WorkOrderComment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)

    entry = WorkOrderUpdate(
        work_order_id=wo.id,
        user_id=current_user.id,
        message=payload.message,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
