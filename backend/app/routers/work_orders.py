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

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.audit_log import AuditLog
from app.routers.vendors import _access as _vendor_menu_access
from app.services.menu_resolver import permission_allows_user
from app.services.audit import append_audit_log
from app.services.unit_inspections import get_inspection as get_authorized_inspection
from app.services.report_delivery import ReportDeliveryError
from app.models.work_order import (
    WorkOrder,
    WorkOrderUpdate,
    WorkOrderTimeEntry,
    WorkOrderTimeCorrection,
    WorkOrderStatus,
    WorkOrderPriority,
    WorkOrderCategory,
)
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderDetail,
    WorkOrderUpdateFields,
    WorkOrderAssign,
    WorkOrderReject,
    WorkOrderRecall,
    WorkOrderEta,
    WorkOrderTimeCreate,
    WorkOrderTimeOut,
    WorkOrderTimeCorrectionCreate,
    WorkOrderTimeCorrectionDecision,
    WorkOrderTimeCorrectionOut,
    WorkOrderVendorAssign,
    WorkOrderVendorOut,
    WorkOrderComplete,
    WorkOrderCancel,
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
    audit_reason=None,
    audit_metadata=None,
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
    if from_status is not None or to_status is not None:
        append_audit_log(
            db, user_id=user.id, organization_id=user.organization_id,
            entity_type="work_order", entity_id=wo.id, action="status_transition",
            old_value={"status": from_status.value if from_status is not None else None},
            new_value={
                "status": to_status.value if to_status is not None else None,
                **({"reason": audit_reason} if audit_reason else {}),
                **(audit_metadata or {}),
            },
        )


def _get_property_for_work_order(db: Session, wo: WorkOrder) -> Property:
    unit = db.query(Unit).filter(Unit.id == wo.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    prop = db.query(Property).filter(Property.id == unit.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


def _require_active_dispatch_location(db: Session, wo: WorkOrder) -> Property:
    """Fail closed when property/unit retires between dispatch and crew start."""
    prop = _get_property_for_work_order(db, wo)
    if (not prop.is_active or prop.deleted_at is not None
            or db.query(Unit.id).filter(
                Unit.id == wo.unit_id, Unit.property_id == prop.id,
                Unit.is_active.is_(True), Unit.deleted_at.is_(None),
            ).first() is None):
        raise HTTPException(status_code=409, detail="Cannot dispatch or start at inactive property or unit")
    return prop


def _user_can_access_work_order(db: Session, user: User, wo: WorkOrder) -> bool:
    """Authorize against the actual Unit->Property, not an untrusted row label."""
    prop = _get_property_for_work_order(db, wo)
    if prop.organization_id != user.organization_id or wo.property_id != prop.id:
        return False

    if user.role == UserRole.TENANT:
        return (wo.tenant_id == user.id and (
            wo.request_origin is None or (
                wo.request_origin == "tenant" and wo.requested_by_user_id == user.id
            )
        ))

    if user.role == UserRole.CREW:
        if wo.assigned_to_id != user.id:
            return False
        return db.query(PropertyAssignment).filter(
            PropertyAssignment.property_id == prop.id,
            PropertyAssignment.user_id == user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        ).first() is not None

    if user.role in (UserRole.ADMIN, UserRole.OWNER):
        return True

    if user.role == UserRole.MANAGER:
        assigned = (
            db.query(PropertyAssignment)
            .filter(
                PropertyAssignment.property_id == prop.id,
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
                PropertyAssignment.deleted_at.is_(None),
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
    """Fail closed on organization and actual Unit->Property for every role."""
    q = (
        db.query(WorkOrder)
        .join(Unit, Unit.id == WorkOrder.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == user.organization_id,
            WorkOrder.property_id == Property.id,
        )
    )

    if user.role == UserRole.TENANT:
        return q.filter(
            WorkOrder.tenant_id == user.id,
            or_(
                WorkOrder.request_origin.is_(None),
                and_(WorkOrder.request_origin == "tenant", WorkOrder.requested_by_user_id == user.id),
            ),
        )

    if user.role == UserRole.CREW:
        return q.join(
            PropertyAssignment, PropertyAssignment.property_id == Property.id,
        ).filter(
            WorkOrder.assigned_to_id == user.id,
            PropertyAssignment.user_id == user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )

    if user.role in (UserRole.ADMIN, UserRole.OWNER):
        return q

    if user.role == UserRole.MANAGER:
        return (
            q.join(PropertyAssignment, PropertyAssignment.property_id == Property.id)
            .filter(
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
                PropertyAssignment.deleted_at.is_(None),
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
    if prop.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Unit is outside your organization")
    if (
        not unit.is_active or unit.deleted_at is not None
        or not prop.is_active or prop.deleted_at is not None
    ):
        raise HTTPException(status_code=404, detail="Unit is not available for maintenance requests")

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
        # Staff-originated maintenance has no actual unit tenant. The real
        # requester is recorded separately and tenant visibility stays denied.
        tenant_id = None

    # A follow-up must reference an authorized, actual inspection of this
    # same unit and property. Never trust a client-supplied inspection ID.
    if payload.source_inspection_id is not None:
        _require_role(current_user, UserRole.ADMIN, UserRole.MANAGER)
        try:
            inspection = get_authorized_inspection(
                db, actor=current_user, inspection_id=payload.source_inspection_id,
            )
        except ReportDeliveryError as exc:
            raise HTTPException(status_code=404, detail="Inspection not available") from exc
        if inspection.unit_id != unit.id or inspection.property_id != prop.id:
            raise HTTPException(status_code=404, detail="Inspection not available")

    wo = WorkOrder(
        unit_id=unit.id,
        property_id=prop.id,
        tenant_id=tenant_id,
        request_origin="tenant" if current_user.role == UserRole.TENANT else "staff",
        requested_by_user_id=current_user.id,
        source_inspection_id=payload.source_inspection_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        permission_to_enter=payload.permission_to_enter,
        entry_notes=payload.entry_notes,
        photo_urls=payload.photo_urls,
        status=WorkOrderStatus.SUBMITTED,
    )
    # The created row and its first activity event must survive or fail as one.
    db.add(wo)
    db.flush()
    _log_update(
        db, wo, current_user, to_status=WorkOrderStatus.SUBMITTED,
        message="Work order submitted",
        audit_metadata={
            "request_origin": "tenant" if current_user.role == UserRole.TENANT else "staff",
            "requested_by_user_id": current_user.id,
            **({"source_inspection_id": payload.source_inspection_id} if payload.source_inspection_id is not None else {}),
        },
    )
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# LIST WORK ORDERS
# ------------------------------------------------------------
def _scoped_work_order_outputs(db: Session, user: User, rows: list[WorkOrder]) -> list[WorkOrderOut]:
    """Attach current names only AFTER the work orders have passed role scope."""
    if not rows:
        return []
    prop_ids = {row.property_id for row in rows}
    unit_ids = {row.unit_id for row in rows}
    properties = db.query(Property).filter(
        Property.id.in_(prop_ids),
        Property.organization_id == user.organization_id,
    ).all()
    names = {prop.id: prop.name for prop in properties}
    units = db.query(Unit).filter(
        Unit.id.in_(unit_ids), Unit.property_id.in_(prop_ids),
    ).all()
    numbers = {unit.id: (unit.property_id, unit.unit_number) for unit in units}
    return [
        WorkOrderOut.model_validate(row).model_copy(update={
            "property_name": names.get(row.property_id),
            "unit_number": (
                numbers[row.unit_id][1]
                if row.unit_id in numbers
                and numbers[row.unit_id][0] == row.property_id
                and row.property_id in names else None
            ),
        })
        for row in rows
    ]


@router.get("", response_model=List[WorkOrderOut])
def list_work_orders(
    status: WorkOrderStatus | None = None,
    priority: WorkOrderPriority | None = None,
    category: WorkOrderCategory | None = None,
    assignment_response: Literal["pending", "accepted", "rejected", "recalled", "legacy"] | None = None,
    property_id: Annotated[int | None, Query(ge=1)] = None,
    search: Annotated[str | None, Query(min_length=2, max_length=80)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accessible maintenance queue with optional bounded, literal search.

    Existing unfiltered callers continue to receive the complete list.
    Search also matches property names and unit numbers only on already
    authorized Unit-to-Property joins.
    When limit is supplied, the sort includes a stable ID tie-breaker so
    adjacent pages do not randomly repeat same-timestamp work orders.
    All filters are applied *after* tenant/crew/org/property visibility.
    """
    q = _visible_work_orders(db, current_user)
    if status is not None:
        q = q.filter(WorkOrder.status == status)
    if priority is not None:
        q = q.filter(WorkOrder.priority == priority)
    if category is not None:
        q = q.filter(WorkOrder.category == category)
    if property_id is not None:
        q = q.filter(WorkOrder.property_id == property_id)
    if assignment_response == "legacy":
        q = q.filter(WorkOrder.assignment_response.is_(None))
    elif assignment_response is not None:
        q = q.filter(WorkOrder.assignment_response == assignment_response)
    if search is not None:
        phrase = search.strip()
        if phrase:
            q = q.filter(or_(
                WorkOrder.title.icontains(phrase, autoescape=True),
                WorkOrder.description.icontains(phrase, autoescape=True),
                Property.name.icontains(phrase, autoescape=True),
                Unit.unit_number.icontains(phrase, autoescape=True),
            ))
    if assignment_response in ("pending", "rejected", "recalled"):
        urgency = case(
            (WorkOrder.priority == WorkOrderPriority.EMERGENCY, 0),
            (WorkOrder.priority == WorkOrderPriority.HIGH, 1),
            (WorkOrder.priority == WorkOrderPriority.MEDIUM, 2), else_=3,
        )
        q = q.order_by(urgency, WorkOrder.created_at.asc(), WorkOrder.id.asc())
    else:
        q = q.order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
    if offset:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    return _scoped_work_order_outputs(db, current_user, q.all())


@router.get("/triage", response_model=List[WorkOrderOut])
def emergency_work_order_triage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Up to twenty visible emergency work orders; not an SLA or dispatch engine.

    Submitted/unacknowledged emergencies appear before other open emergency
    work. Oldest first within each group; exact ID tie-break is deterministic.
    Tenant, manager, crew and organization access is identical to the queue.
    """
    rows = (
        _visible_work_orders(db, current_user)
        .filter(
            WorkOrder.priority == WorkOrderPriority.EMERGENCY,
            WorkOrder.status.notin_((WorkOrderStatus.CLOSED, WorkOrderStatus.CANCELLED)),
        )
        .order_by(
            (WorkOrder.status != WorkOrderStatus.SUBMITTED).asc(),
            WorkOrder.created_at.asc(), WorkOrder.id.asc(),
        )
        .limit(20).all()
    )
    return _scoped_work_order_outputs(db, current_user, rows)


@router.get("/summary")
def work_order_queue_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Organization- and role-scoped read-only queue metrics."""
    visible = _visible_work_orders(db, current_user)
    active = WorkOrder.status.notin_((WorkOrderStatus.CLOSED, WorkOrderStatus.CANCELLED))
    def count(q) -> int:
        return int(q.with_entities(func.count(func.distinct(WorkOrder.id))).scalar() or 0)
    return {
        "open": count(visible.filter(active)),
        "emergency_open": count(visible.filter(active, WorkOrder.priority == WorkOrderPriority.EMERGENCY)),
        "awaiting_assignment": count(visible.filter(WorkOrder.status == WorkOrderStatus.ACKNOWLEDGED, WorkOrder.assigned_to_id.is_(None))),
        "pending_crew_response": count(visible.filter(WorkOrder.status == WorkOrderStatus.ASSIGNED, WorkOrder.assignment_response == "pending")),
        "declined_assignment": count(visible.filter(WorkOrder.status == WorkOrderStatus.ACKNOWLEDGED, WorkOrder.assignment_response == "rejected")),
        "recalled_assignment": count(visible.filter(WorkOrder.status == WorkOrderStatus.ACKNOWLEDGED, WorkOrder.assignment_response == "recalled")),
        "in_progress": count(visible.filter(WorkOrder.status == WorkOrderStatus.IN_PROGRESS)),
        "ready_to_close": count(visible.filter(WorkOrder.status == WorkOrderStatus.COMPLETED)),
    }


@router.get("/possible-duplicates")
def possible_duplicate_work_orders(
    unit_id: Annotated[int, Query(ge=1)],
    title: Annotated[str, Query(min_length=3, max_length=80)],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest similar open work orders already authorized to the actor.

    An unrelated tenant's issue must never be exposed even if it targets the
    same unit. This is an advisory lookup and cannot silently reject intake.
    """
    term = title.strip()
    if len(term) < 3:
        raise HTTPException(status_code=422, detail="Use at least three non-space characters.")
    rows = (
        _visible_work_orders(db, current_user)
        .filter(
            WorkOrder.unit_id == unit_id,
            WorkOrder.status.notin_((WorkOrderStatus.CLOSED, WorkOrderStatus.CANCELLED)),
            WorkOrder.title.icontains(term, autoescape=True),
        )
        .order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
        .limit(5)
        .all()
    )
    return [
        {"id":row.id, "title":row.title, "status":row.status,
         "priority":row.priority}
        for row in rows
    ]


@router.get("/request-units")
def requestable_work_order_units(
    search: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Minimal unit choices, scoped to a user's actual maintenance intake rights."""
    from app.models.lease import Lease, LeaseStatus

    query = (
        db.query(Unit.id, Unit.unit_number, Property.id, Property.name)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == current_user.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
    )
    if current_user.role == UserRole.TENANT:
        query = query.join(Lease, Lease.unit_id == Unit.id).filter(
            Lease.tenant_id == current_user.id, Lease.status == LeaseStatus.ACTIVE)
    elif current_user.role == UserRole.MANAGER:
        query = query.join(PropertyAssignment, PropertyAssignment.property_id == Property.id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None))
    elif current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        return []
    if search:
        term = search.strip()
        if term:
            query = query.filter(or_(
                Property.name.icontains(term, autoescape=True),
                Unit.unit_number.icontains(term, autoescape=True)))
    rows = query.distinct().order_by(Property.name, Unit.unit_number, Unit.id).offset(offset).limit(limit).all()
    return [{"id":item[0], "unit_number":item[1], "property_id":item[2],
             "property_name":item[3]} for item in rows]


def _vendor_work_order_access(db: Session, user: User) -> int:
    # Deny before reading WorkOrder IDs; legacy tenant/crew routes unchanged.
    org_id = _vendor_menu_access(db, user)
    if not permission_allows_user(db, user=user, menu_key="MAINTENANCE.WORK_ORDERS"):
        raise HTTPException(status_code=403, detail="Maintenance work order access required.")
    return org_id


def _vendor_work_order_out(row: WorkOrder) -> WorkOrderVendorOut:
    # Deliberately omit tenant names, entry instructions, photographs and
    # company data; the picker calls the existing authorized vendor list.
    return WorkOrderVendorOut(
        id=row.id, property_id=row.property_id, title=row.title,
        status=row.status, assigned_to_id=row.assigned_to_id,
        vendor_id=row.vendor_id,
    )


@router.get("/vendor-assignments", response_model=list[WorkOrderVendorOut])
def list_vendor_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _vendor_work_order_access(db, current_user)
    # WorkOrder organization is derived from its actual Unit->Property.
    rows = (
        db.query(WorkOrder)
        .join(Unit, Unit.id == WorkOrder.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == org_id,
            WorkOrder.property_id == Property.id,
        )
        .order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
        .limit(1001).all()
    )
    if len(rows) > 1000:
        raise HTTPException(status_code=422, detail="Too many work orders for vendor selection.")
    return [_vendor_work_order_out(row) for row in rows]


@router.post("/{wo_id}/vendor", response_model=WorkOrderVendorOut)
def set_work_order_vendor(
    wo_id: int,
    payload: WorkOrderVendorAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _vendor_work_order_access(db, current_user)
    row = (
        db.query(WorkOrder)
        .join(Unit, Unit.id == WorkOrder.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            WorkOrder.id == wo_id,
            Property.organization_id == org_id,
            WorkOrder.property_id == Property.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Work order not found.")
    if row.status in (WorkOrderStatus.CLOSED, WorkOrderStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="A completed work order cannot change vendor assignment.")
    if payload.vendor_id is not None:
        vendor = db.query(Vendor).filter(
            Vendor.id == payload.vendor_id,
            Vendor.organization_id == org_id,
            Vendor.is_active.is_(True),
            Vendor.deleted_at.is_(None),
        ).first()
        if vendor is None:
            raise HTTPException(status_code=404, detail="Vendor company not found.")
    if row.vendor_id == payload.vendor_id:
        return _vendor_work_order_out(row)
    previous = row.vendor_id
    row.vendor_id = payload.vendor_id
    _log_update(
        db, row, current_user,
        message="Vendor company linked" if payload.vendor_id is not None
        else "Vendor company unlinked",
    )
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="work_order", entity_id=row.id, action="vendor_assigned",
        old_value={"vendor_id": previous}, new_value={"vendor_id": payload.vendor_id},
    )
    db.commit()
    db.refresh(row)
    return _vendor_work_order_out(row)


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
    # Never resolve labels for a work order the caller cannot read.
    prop = _get_property_for_work_order(db, wo)
    unit = db.query(Unit).filter(Unit.id == wo.unit_id).first()
    detail = WorkOrderDetail.model_validate(wo)
    source_inspection_id = None
    if wo.source_inspection_id is not None and current_user.role in (
        UserRole.ADMIN, UserRole.MANAGER,
    ):
        try:
            inspection = get_authorized_inspection(
                db, actor=current_user, inspection_id=wo.source_inspection_id,
            )
            if inspection.property_id == prop.id and inspection.unit_id == wo.unit_id:
                source_inspection_id = wo.source_inspection_id
        except ReportDeliveryError:
            pass  # Do not reveal an inspection that is outside this viewer's scope.
    creation_audits = db.query(AuditLog).filter(
        AuditLog.organization_id == prop.organization_id,
        AuditLog.entity_type == "work_order",
        AuditLog.entity_id == wo.id,
        AuditLog.action == "status_transition",
    ).order_by(AuditLog.id.asc()).all()
    request_origin = "unknown_legacy"
    requested_by_user_id = None
    for record in creation_audits:
        try:
            evidence = json.loads(record.new_value or "null")
        except (TypeError, ValueError):
            continue
        if not isinstance(evidence, dict) or evidence.get("status") != "submitted":
            continue
        origin, actor_id = evidence.get("request_origin"), evidence.get("requested_by_user_id")
        if origin not in ("tenant", "staff") or type(actor_id) is not int or record.user_id != actor_id:
            continue
        requested_by_user_id, request_origin = actor_id, origin
        break
    actor_ids = {row.user_id for row in detail.updates}
    actors = (
        db.query(User).filter(
            User.id.in_(actor_ids),
            User.organization_id == prop.organization_id,
        ).all() if actor_ids else []
    )
    actor_names = {actor.id: f"{actor.first_name} {actor.last_name}".strip() for actor in actors}
    return detail.model_copy(update={
        "property_name": prop.name,
        "unit_number": unit.unit_number if unit is not None else None,
        "request_origin": request_origin,
        "requested_by_user_id": requested_by_user_id,
        "source_inspection_id": source_inspection_id,
        "updates": [
            row.model_copy(update={"actor_name": actor_names.get(row.user_id)})
            for row in detail.updates
        ],
    })


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
    if "status" in changes:
        raise HTTPException(
            status_code=409,
            detail="Use the explicit work-order lifecycle actions to change status.",
        )
    if not changes:
        return wo

    # Retain before/after evidence and the activity entry atomically with
    # the business update; generic PATCH is not an alternate status flow.
    before = {field: getattr(wo, field) for field in changes}
    for field, value in changes.items():
        setattr(wo, field, value)
    _log_update(db, wo, current_user, message=f"Updated fields: {', '.join(changes.keys())}")
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="updated",
        old_value=before, new_value=changes,
    )
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

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)
    if wo.status not in (WorkOrderStatus.ACKNOWLEDGED, WorkOrderStatus.ASSIGNED):
        raise HTTPException(
            status_code=409,
            detail="Acknowledge the work order before assigning; active or finished work cannot be reassigned.",
        )

    # Verify the crew member exists, is crew, active, and assigned to this property
    crew = db.query(User).filter(User.id == payload.crew_user_id).first()
    if (not crew or crew.role != UserRole.CREW or not crew.is_active
            or crew.deleted_at is not None):
        raise HTTPException(status_code=400, detail="Invalid or inactive crew member")
    # Both original offers and later crew execution revalidate live inventory.
    prop = _require_active_dispatch_location(db, wo)
    if crew.organization_id != prop.organization_id:
        raise HTTPException(status_code=403, detail="Crew member is not in this organization")

    assigned = (
        db.query(PropertyAssignment)
        .filter(
            PropertyAssignment.property_id == wo.property_id,
            PropertyAssignment.user_id == crew.id,
            PropertyAssignment.is_active == True,  # noqa: E712
            PropertyAssignment.deleted_at.is_(None),
        )
        .first()
    )
    if not assigned:
        raise HTTPException(status_code=400, detail="Crew member is not assigned to this property")
    if wo.status == WorkOrderStatus.ASSIGNED and wo.assigned_to_id == crew.id:
        return wo

    old = wo.status
    previous_crew_id = wo.assigned_to_id
    previous_eta = wo.crew_eta_at.isoformat() + "Z" if wo.crew_eta_at is not None else None
    wo.assigned_to_id = crew.id
    wo.assigned_at = datetime.utcnow()
    wo.assigned_by_id = current_user.id
    wo.assignment_response = "pending"
    wo.assignment_responded_at = None
    wo.crew_eta_at = None
    wo.status = WorkOrderStatus.ASSIGNED

    _log_update(
        db, wo, current_user,
        from_status=old, to_status=wo.status,
        message=f"Assigned to {crew.first_name} {crew.last_name}",
    )
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_assignment",
        old_value={"assigned_to_id": previous_crew_id, "crew_eta_at": previous_eta},
        new_value={"assigned_to_id": crew.id, "assignment_response": "pending", "crew_eta_at": None},
    )
    db.commit()
    db.refresh(wo)
    return wo



# ------------------------------------------------------------
# CREW DISPATCH DECISION (no automatic escalation or tenant consent)
# ------------------------------------------------------------
def _crew_assignment_for_decision(db: Session, wo_id: int, current_user: User) -> WorkOrder:
    if (current_user.role != UserRole.CREW or not current_user.is_active
            or current_user.deleted_at is not None):
        raise HTTPException(status_code=403, detail="Active crew membership required")
    # Lock against staff reassignment and a concurrent accept/reject/start.
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    if wo.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the currently assigned crew may respond")
    _check_access(db, current_user, wo)
    if wo.status != WorkOrderStatus.ASSIGNED:
        raise HTTPException(status_code=409, detail="Assignment is no longer awaiting crew action")
    return wo


@router.post("/{wo_id}/accept", response_model=WorkOrderOut)
def accept_work_order_assignment(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = _crew_assignment_for_decision(db, wo_id, current_user)
    if wo.assignment_response == "accepted":
        return wo
    if wo.assignment_response != "pending":
        raise HTTPException(status_code=409, detail="This assignment is not awaiting acceptance")
    _require_active_dispatch_location(db, wo)
    wo.assignment_response = "accepted"
    wo.assignment_responded_at = datetime.utcnow()
    _log_update(db, wo, current_user, message="Crew accepted assignment")
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_assignment_accepted",
        old_value={"assigned_to_id": wo.assigned_to_id, "response": "pending"},
        new_value={"assigned_to_id": current_user.id, "response": "accepted"},
    )
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{wo_id}/reject", response_model=WorkOrderOut)
def reject_work_order_assignment(
    wo_id: int,
    payload: WorkOrderReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = _crew_assignment_for_decision(db, wo_id, current_user)
    if wo.assignment_response != "pending":
        raise HTTPException(status_code=409, detail="This assignment is not awaiting rejection")
    reason = payload.reason.strip()
    if not 5 <= len(reason) <= 1000:
        raise HTTPException(status_code=422, detail="Provide a 5-1000 character rejection reason")
    prior_status = wo.status
    previous_crew = wo.assigned_to_id
    previous_eta = wo.crew_eta_at.isoformat() + "Z" if wo.crew_eta_at is not None else None
    wo.assigned_to_id = None
    wo.assigned_at = None
    wo.assigned_by_id = None
    wo.assignment_response = "rejected"
    wo.assignment_responded_at = datetime.utcnow()
    wo.crew_eta_at = None
    wo.status = WorkOrderStatus.ACKNOWLEDGED
    _log_update(
        db, wo, current_user,
        from_status=prior_status, to_status=wo.status,
        message="Crew declined assignment: " + reason,
        audit_reason=reason,
    )
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_assignment_rejected",
        old_value={"assigned_to_id": previous_crew, "response": "pending", "crew_eta_at": previous_eta},
        new_value={"assigned_to_id": None, "response": "rejected", "reason": reason, "crew_eta_at": None},
    )
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# STAFF RECALL OF UNSTARTED CREW OFFER
# ------------------------------------------------------------
@router.post("/{wo_id}/recall", response_model=WorkOrderOut)
def recall_work_order_assignment(
    wo_id: int,
    payload: WorkOrderRecall,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Withdraw unstarted dispatch without cancelling the work order or blaming crew."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)
    if (wo.status != WorkOrderStatus.ASSIGNED or wo.assigned_to_id is None
            or wo.assignment_response not in (None, "pending", "accepted")):
        raise HTTPException(status_code=409, detail="Only an unstarted assigned crew dispatch can be recalled")
    reason = payload.reason.strip()
    if not 5 <= len(reason) <= 1000:
        raise HTTPException(status_code=422, detail="Provide a 5-1000 character recall reason")
    previous_crew = wo.assigned_to_id
    previous_response = wo.assignment_response
    wo.assigned_to_id = None
    wo.assigned_at = None
    wo.assigned_by_id = None
    wo.assignment_response = "recalled"
    wo.assignment_responded_at = datetime.utcnow()
    previous_eta = wo.crew_eta_at.isoformat() + "Z" if wo.crew_eta_at is not None else None
    wo.crew_eta_at = None
    wo.status = WorkOrderStatus.ACKNOWLEDGED
    _log_update(
        db, wo, current_user, from_status=WorkOrderStatus.ASSIGNED,
        to_status=wo.status, message="Staff recalled crew assignment: " + reason,
        audit_reason=reason,
    )
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_assignment_recalled",
        old_value={"assigned_to_id": previous_crew, "response": previous_response, "crew_eta_at": previous_eta},
        new_value={"assigned_to_id": None, "response": "recalled", "reason": reason, "crew_eta_at": None},
    )
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# CREW ARRIVAL ETA AFTER ACCEPTANCE
# ------------------------------------------------------------
@router.post("/{wo_id}/eta", response_model=WorkOrderOut)
def update_crew_eta(
    wo_id: int,
    payload: WorkOrderEta,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = _crew_assignment_for_decision(db, wo_id, current_user)
    if wo.assignment_response != "accepted":
        raise HTTPException(status_code=409, detail="Accept assignment before setting arrival ETA")
    _require_active_dispatch_location(db, wo)
    if payload.eta_at.tzinfo is None or payload.eta_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="Arrival ETA requires a timezone offset")
    utc = datetime.now(timezone.utc)
    provided = payload.eta_at.astimezone(timezone.utc)
    if not utc < provided <= utc + timedelta(days=30):
        raise HTTPException(status_code=422, detail="Arrival ETA must be future and within 30 days")
    normalized = provided.replace(tzinfo=None)
    if wo.crew_eta_at == normalized:
        return wo
    previous = wo.crew_eta_at.isoformat() + "Z" if wo.crew_eta_at is not None else None
    wo.crew_eta_at = normalized
    _log_update(db, wo, current_user, message="Crew updated estimated arrival (UTC): " + normalized.isoformat() + "Z")
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_eta_updated",
        old_value={"crew_eta_at": previous},
        new_value={"crew_eta_at": normalized.isoformat() + "Z"},
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
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    # Only the assigned crew member can start
    if current_user.role != UserRole.CREW or wo.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned crew member can start work")
    # Assignment ID alone is not authority for a different organization.
    _check_access(db, current_user, wo)

    if wo.status != WorkOrderStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail=f"Cannot start from status '{wo.status.value}'")

    if wo.assignment_response == "pending":
        raise HTTPException(status_code=409, detail="Crew must accept the assignment before starting")
    if wo.assignment_response not in (None, "accepted"):
        raise HTTPException(status_code=409, detail="Only accepted or historical assignments can start")
    _require_active_dispatch_location(db, wo)

    old = wo.status
    wo.status = WorkOrderStatus.IN_PROGRESS

    _log_update(db, wo, current_user, from_status=old, to_status=wo.status, message="Work started")
    db.commit()
    db.refresh(wo)
    return wo


# ------------------------------------------------------------
# TIME LOGS: IMMUTABLE BY API, NEVER MONEY OR APPROVED PAYROLL
# ------------------------------------------------------------
def _require_crew_time_access(db: Session, wo: WorkOrder, user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER, UserRole.CREW):
        raise HTTPException(status_code=403, detail="Crew time records are staff-only")
    _check_access(db, user, wo)


@router.get("/{wo_id}/time-entries", response_model=List[WorkOrderTimeOut])
def list_work_order_time_entries(
    wo_id: int,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    _require_crew_time_access(db, wo, current_user)
    return db.query(WorkOrderTimeEntry).filter(
        WorkOrderTimeEntry.work_order_id == wo.id,
    ).order_by(WorkOrderTimeEntry.started_at.asc(), WorkOrderTimeEntry.id.asc()).offset(offset).limit(limit).all()


@router.post("/{wo_id}/time-entries", response_model=WorkOrderTimeOut, status_code=status.HTTP_201_CREATED)
def create_work_order_time_entry(
    wo_id: int,
    payload: WorkOrderTimeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.CREW:
        raise HTTPException(status_code=403, detail="Only assigned crew can log their own hours")
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    _check_access(db, current_user, wo)
    if wo.assigned_to_id != current_user.id or wo.status != WorkOrderStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Crew time requires currently assigned in-progress work")
    if (payload.started_at.tzinfo is None or payload.started_at.utcoffset() is None
            or payload.ended_at.tzinfo is None or payload.ended_at.utcoffset() is None):
        raise HTTPException(status_code=422, detail="Crew time requires timezone-aware timestamps")
    start = payload.started_at.astimezone(timezone.utc).replace(tzinfo=None)
    end = payload.ended_at.astimezone(timezone.utc).replace(tzinfo=None)
    delta = (end - start).total_seconds()
    if delta < 60 or delta > 86400 or delta % 60 != 0 or end > datetime.utcnow():
        raise HTTPException(status_code=422, detail="Record 1-1440 past whole minutes with start before end")
    note = payload.notes.strip() if payload.notes is not None else None
    overlap = db.query(WorkOrderTimeEntry).filter(
        WorkOrderTimeEntry.work_order_id == wo.id,
        WorkOrderTimeEntry.crew_user_id == current_user.id,
        WorkOrderTimeEntry.started_at < end,
        WorkOrderTimeEntry.ended_at > start,
    ).first()
    if overlap is not None:
        if overlap.started_at == start and overlap.ended_at == end and overlap.notes == note:
            return overlap
        raise HTTPException(status_code=409, detail="This time interval overlaps another crew entry")
    row = WorkOrderTimeEntry(
        work_order_id=wo.id, crew_user_id=current_user.id,
        started_at=start, ended_at=end, duration_minutes=int(delta // 60), notes=note,
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_time_recorded",
        new_value={"time_entry_id": row.id, "crew_user_id": current_user.id,
                   "started_at": start.isoformat() + "Z",
                   "ended_at": end.isoformat() + "Z",
                   "duration_minutes": row.duration_minutes},
    )
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------------
# AUDITED CREW TIME CORRECTION REQUEST / INDEPENDENT REVIEW
# ------------------------------------------------------------
@router.get("/{wo_id}/time-corrections", response_model=List[WorkOrderTimeCorrectionOut])
def list_work_order_time_corrections(
    wo_id: int,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    _require_crew_time_access(db, wo, current_user)
    return db.query(WorkOrderTimeCorrection).filter(
        WorkOrderTimeCorrection.work_order_id == wo_id,
    ).order_by(WorkOrderTimeCorrection.id.asc()).offset(offset).limit(limit).all()


@router.post("/{wo_id}/time-entries/{entry_id}/corrections",
             response_model=WorkOrderTimeCorrectionOut, status_code=201)
def request_work_order_time_correction(
    wo_id: int, entry_id: int, payload: WorkOrderTimeCorrectionCreate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.CREW:
        raise HTTPException(status_code=403, detail="Only original crew can request a correction")
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    _require_crew_time_access(db, wo, current_user)
    entry = db.query(WorkOrderTimeEntry).filter(
        WorkOrderTimeEntry.id == entry_id, WorkOrderTimeEntry.work_order_id == wo_id,
    ).first()
    if entry is None or entry.crew_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Crew time entry not found")
    if (payload.started_at.tzinfo is None or payload.started_at.utcoffset() is None
            or payload.ended_at.tzinfo is None or payload.ended_at.utcoffset() is None):
        raise HTTPException(status_code=422, detail="Correction timestamps must contain timezones")
    start = payload.started_at.astimezone(timezone.utc).replace(tzinfo=None)
    end = payload.ended_at.astimezone(timezone.utc).replace(tzinfo=None)
    seconds = (end - start).total_seconds()
    if seconds < 60 or seconds > 86400 or seconds % 60 != 0 or end > datetime.utcnow():
        raise HTTPException(status_code=422, detail="Corrected time must be 1-1440 completed whole minutes")
    reason = payload.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Correction reason is required")
    if start == entry.started_at and end == entry.ended_at:
        raise HTTPException(status_code=409, detail="Correction must change the time evidence")
    pending = db.query(WorkOrderTimeCorrection).filter(
        WorkOrderTimeCorrection.time_entry_id == entry.id,
        WorkOrderTimeCorrection.status == "pending",
    ).first()
    if pending is not None:
        if pending.proposed_started_at == start and pending.proposed_ended_at == end and pending.reason == reason:
            return pending
        raise HTTPException(status_code=409, detail="Time correction already awaiting review")
    row = WorkOrderTimeCorrection(
        work_order_id=wo.id, time_entry_id=entry.id, requested_by_user_id=current_user.id,
        proposed_started_at=start, proposed_ended_at=end, duration_minutes=int(seconds // 60),
        reason=reason, status="pending",
    )
    db.add(row); db.flush()
    db.add(WorkOrderUpdate(work_order_id=wo.id, user_id=current_user.id,
                           message=f"Crew time correction #{row.id} requested for entry #{entry.id}"))
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_time_correction_requested",
        old_value={"entry_id": entry.id, "started_at": entry.started_at,
                   "ended_at": entry.ended_at, "minutes": entry.duration_minutes},
        new_value={"correction_id": row.id, "started_at": start, "ended_at": end,
                   "minutes": row.duration_minutes, "reason": reason},
    )
    db.commit(); db.refresh(row)
    return row


@router.post("/{wo_id}/time-corrections/{correction_id}/decision",
             response_model=WorkOrderTimeCorrectionOut)
def review_work_order_time_correction(
    wo_id: int, correction_id: int, payload: WorkOrderTimeCorrectionDecision,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).with_for_update().first()
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    _require_crew_time_access(db, wo, current_user)
    row = db.query(WorkOrderTimeCorrection).filter(
        WorkOrderTimeCorrection.id == correction_id,
        WorkOrderTimeCorrection.work_order_id == wo_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Correction not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Correction already reviewed")
    reason = payload.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Review reason is required")
    entry = db.query(WorkOrderTimeEntry).filter(
        WorkOrderTimeEntry.id == row.time_entry_id,
        WorkOrderTimeEntry.work_order_id == wo_id,
    ).first()
    if entry is None or entry.crew_user_id != row.requested_by_user_id:
        raise HTTPException(status_code=409, detail="Invalid correction evidence")
    if payload.approve:
        for other in db.query(WorkOrderTimeEntry).filter(
            WorkOrderTimeEntry.work_order_id == wo_id,
            WorkOrderTimeEntry.crew_user_id == entry.crew_user_id,
            WorkOrderTimeEntry.id != entry.id,
        ).all():
            accepted = db.query(WorkOrderTimeCorrection).filter(
                WorkOrderTimeCorrection.time_entry_id == other.id,
                WorkOrderTimeCorrection.status == "approved",
            ).order_by(WorkOrderTimeCorrection.id.desc()).first()
            start = accepted.proposed_started_at if accepted is not None else other.started_at
            end = accepted.proposed_ended_at if accepted is not None else other.ended_at
            if start < row.proposed_ended_at and end > row.proposed_started_at:
                raise HTTPException(status_code=409, detail="Corrected interval overlaps other crew time")
    row.status = "approved" if payload.approve else "denied"
    row.reviewed_by_user_id = current_user.id
    row.reviewed_at = datetime.utcnow()
    row.review_reason = reason
    db.add(WorkOrderUpdate(work_order_id=wo.id, user_id=current_user.id,
                           message=f"Crew time correction #{row.id} {row.status}"))
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="crew_time_correction_reviewed",
        old_value={"correction_id": row.id, "status": "pending"},
        new_value={"correction_id": row.id, "status": row.status, "reason": reason,
                   "original_minutes": entry.duration_minutes,
                   "corrected_minutes": row.duration_minutes},
    )
    db.commit(); db.refresh(row)
    return row


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
    _check_access(db, current_user, wo)

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
    payload: WorkOrderCancel | None = None,
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

    reason = payload.reason.strip() if payload is not None and payload.reason else None
    if payload is not None and payload.reason is not None and len(reason) < 5:
        raise HTTPException(status_code=422, detail="Cancellation reason must be at least five non-space characters")

    old = wo.status
    wo.status = WorkOrderStatus.CANCELLED

    _log_update(
        db, wo, current_user, from_status=old, to_status=wo.status,
        message="Cancelled" + (": " + reason if reason else ""),
        audit_reason=reason,
    )
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

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Activity note cannot be blank")

    entry = WorkOrderUpdate(
        work_order_id=wo.id,
        user_id=current_user.id,
        message=message,
    )
    db.add(entry)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="work_order", entity_id=wo.id, action="comment_added",
        new_value={"activity_id": entry.id},
    )
    db.commit()
    db.refresh(entry)
    return WorkOrderUpdateOut.model_validate(entry).model_copy(update={
        "actor_name": f"{current_user.first_name} {current_user.last_name}".strip(),
    })
