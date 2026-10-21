"""Audited operator-managed dispatch reviews; no automatic messaging or money."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.maintenance_dispatch_review import MaintenanceDispatchReview
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.routers.auth import get_current_user
from app.routers.work_orders import _maintenance_vendor_scope, _check_access
from app.schemas.maintenance_dispatch_review import (
    DispatchReviewOpen, DispatchReviewClose, DispatchReviewOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/maintenance/dispatch-reviews", tags=["Maintenance Dispatch Reviews"])


def _require_staff(db: Session, actor: User) -> None:
    if (
        not actor.is_active or actor.deleted_at is not None
        or actor.organization_id is None
        or actor.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)
    ):
        raise HTTPException(403, "Active dispatch review staff permission required")
    if db.query(Organization.id).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True),
        Organization.deleted_at.is_(None),
    ).first() is None:
        raise HTTPException(403, "Active organization required")


def _require_property_manager(db: Session, actor: User, property_id: int) -> None:
    if actor.role != UserRole.MANAGER:
        return
    if db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == property_id,
        PropertyAssignment.user_id == actor.id,
        PropertyAssignment.role == UserRole.MANAGER,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first() is None:
        raise HTTPException(403, "Current property manager assignment required")


def _scope_order(db: Session, actor: User, work_order_id: int, *, writing: bool):
    _require_staff(db, actor)
    order, prop = _maintenance_vendor_scope(db, work_order_id, actor, write=writing)
    _require_property_manager(db, actor, prop.id)
    return order, prop


def _view(row: MaintenanceDispatchReview) -> DispatchReviewOut:
    # A review case never represents a delivered message or escalation.
    return DispatchReviewOut.model_validate(row)


def list_dispatch_reviews(
    *, db: Session, current_user: User, include_closed: bool = False,
    limit: int = 50, offset: int = 0,
) -> list[DispatchReviewOut]:
    _require_staff(db, current_user)
    if not (1 <= limit <= 100 and 0 <= offset <= 10000):
        raise HTTPException(422, "Review page outside supported range")
    query = (
        db.query(MaintenanceDispatchReview)
        .join(WorkOrder, WorkOrder.id == MaintenanceDispatchReview.work_order_id)
        .join(Unit, Unit.id == WorkOrder.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            MaintenanceDispatchReview.organization_id == current_user.organization_id,
            WorkOrder.property_id == Property.id,
            Property.organization_id == current_user.organization_id,
        )
    )
    if current_user.role == UserRole.MANAGER:
        query = query.join(
            PropertyAssignment, PropertyAssignment.property_id == Property.id,
        ).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.role == UserRole.MANAGER,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
    if not include_closed:
        query = query.filter(MaintenanceDispatchReview.status == "open")
    rows = query.order_by(
        MaintenanceDispatchReview.created_at.asc(),
        MaintenanceDispatchReview.id.asc(),
    ).offset(offset).limit(limit).all()
    return [_view(row) for row in rows]


def open_dispatch_review(
    work_order_id: int, payload: DispatchReviewOpen,
    *, db: Session, current_user: User,
) -> DispatchReviewOut:
    order, prop = _scope_order(db, current_user, work_order_id, writing=True)
    order = db.query(WorkOrder).filter(WorkOrder.id == order.id).with_for_update().one()
    _check_access(db, current_user, order)
    _require_property_manager(db, current_user, prop.id)
    if order.status not in (WorkOrderStatus.SUBMITTED, WorkOrderStatus.ACKNOWLEDGED):
        if not (order.status == WorkOrderStatus.ASSIGNED and order.assignment_response == "pending"):
            raise HTTPException(409, "No unresolved dispatch issue for this work order")
    existing = db.query(MaintenanceDispatchReview).filter(
        MaintenanceDispatchReview.open_work_order_id == order.id,
    ).with_for_update().first()
    if existing is not None:
        if existing.organization_id != current_user.organization_id:
            raise HTTPException(409, "Conflicting dispatch review organization")
        if existing.reason == payload.reason:
            return _view(existing)  # Exact retry, no duplicate event.
        raise HTTPException(409, "Resolve the existing dispatch review before opening another")
    row = MaintenanceDispatchReview(
        organization_id=current_user.organization_id,
        work_order_id=order.id, open_work_order_id=order.id,
        reason=payload.reason, opened_by_user_id=current_user.id,
        status="open",
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id,
        organization_id=current_user.organization_id,
        entity_type="maintenance_dispatch_review", entity_id=row.id,
        action="opened",
        new_value={
            "work_order_id": order.id, "property_id": prop.id,
            "reason": payload.reason, "externally_notified": False,
        },
    )
    db.commit()
    return _view(row)


def close_dispatch_review(
    review_id: int, payload: DispatchReviewClose,
    *, db: Session, current_user: User,
) -> DispatchReviewOut:
    _require_staff(db, current_user)
    row = db.query(MaintenanceDispatchReview).filter(
        MaintenanceDispatchReview.id == review_id,
        MaintenanceDispatchReview.organization_id == current_user.organization_id,
    ).first()
    if row is None:
        raise HTTPException(404, "Dispatch review not available")
    # Read-only location scope allows historic cases to be resolved even
    # after a property/unit is retired; the actor must still be authorized.
    order, prop = _scope_order(db, current_user, row.work_order_id, writing=False)
    db.query(WorkOrder).filter(WorkOrder.id == order.id).with_for_update().one()
    _check_access(db, current_user, order)
    _require_property_manager(db, current_user, prop.id)
    row = db.query(MaintenanceDispatchReview).filter(
        MaintenanceDispatchReview.id == review_id,
        MaintenanceDispatchReview.organization_id == current_user.organization_id,
    ).with_for_update().one()
    if row.status == "closed":
        if row.resolution_note == payload.resolution_note:
            return _view(row)  # Replayed close does not rewrite the audit.
        raise HTTPException(409, "Dispatch review is already closed")
    if row.status != "open" or row.open_work_order_id != order.id:
        raise HTTPException(409, "Inconsistent dispatch review state")
    row.status = "closed"
    row.open_work_order_id = None
    row.closed_by_user_id = current_user.id
    row.closed_at = datetime.utcnow()
    row.resolution_note = payload.resolution_note
    append_audit_log(
        db, user_id=current_user.id,
        organization_id=current_user.organization_id,
        entity_type="maintenance_dispatch_review", entity_id=row.id,
        action="closed",
        old_value={"status": "open", "work_order_id": order.id},
        new_value={
            "status": "closed", "work_order_id": order.id,
            "resolution_note": payload.resolution_note,
            "externally_notified": False,
        },
    )
    db.commit()
    return _view(row)


@router.get("", response_model=list[DispatchReviewOut])
def get_dispatch_reviews(
    include_closed: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_dispatch_reviews(
        db=db, current_user=current_user,
        include_closed=include_closed, limit=limit, offset=offset,
    )


@router.post("/work-orders/{work_order_id}", response_model=DispatchReviewOut, status_code=201)
def post_dispatch_review(
    work_order_id: int, payload: DispatchReviewOpen,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    return open_dispatch_review(work_order_id, payload, db=db, current_user=current_user)


@router.post("/{review_id}/close", response_model=DispatchReviewOut)
def post_close_dispatch_review(
    review_id: int, payload: DispatchReviewClose,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    return close_dispatch_review(review_id, payload, db=db, current_user=current_user)
