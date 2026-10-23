"""Staff procurement approval and attested physical receiving, WITHOUT payables."""
from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.maintenance_material import (
    MaintenanceMaterialOrder as Order, MaintenanceMaterialMovement as Movement,
    MaintenanceMaterialIssue as Issue, MaintenanceMaterialVariance as Variance,
    MaintenanceMaterialVarianceDecision as VarianceDecision,
    MaintenanceMaterialVarianceRestoration as VarianceRestore,
)
from app.models.audit_log import AuditLog
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole, Organization
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder
from app.routers.auth import get_current_user
from app.routers.work_orders import _maintenance_vendor_scope, _check_access
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/maintenance/materials", tags=["Maintenance Materials"])


class NewOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_order_id: int = Field(ge=1)
    request_key: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9-]+$")
    vendor_id: int = Field(ge=1)
    sku: str = Field(min_length=2, max_length=60, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    item_name: str = Field(min_length=3, max_length=255)
    quantity: int = Field(ge=1, le=10000)
    unit_cost_cents: int = Field(ge=0, le=100000000)
    reason: str = Field(min_length=10, max_length=1000)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool
    reason: str = Field(min_length=10, max_length=500)


class Receipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=3, max_length=100)
    quantity: int = Field(ge=1, le=10000)
    notes: str = Field(min_length=10, max_length=1000)


class Correction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=1000)


class IssueStock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_work_order_id: int = Field(ge=1)
    reference: str = Field(min_length=3, max_length=100)
    quantity: int = Field(ge=1, le=10000)
    notes: str = Field(min_length=10, max_length=1000)


class StockVarianceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9-]+$")
    quantity: int = Field(ge=1, le=10000)
    reason: str = Field(min_length=10, max_length=1000)


def _staff(db: Session, user: User) -> None:
    if (not user.is_active or user.deleted_at is not None
            or user.organization_id is None
            or user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)):
        raise HTTPException(403, "Active maintenance staff account required")
    if db.query(Organization.id).filter(
        Organization.id == user.organization_id, Organization.is_active.is_(True),
        Organization.deleted_at.is_(None),
    ).first() is None:
        raise HTTPException(403, "Active company required")


def _work(db: Session, actor: User, work_order_id: int, *, write: bool):
    _staff(db, actor)
    wo, prop = _maintenance_vendor_scope(db, work_order_id, actor, write=write)
    # Global MANAGER role with only a CREW assignment is never procurement authority.
    if actor.role == UserRole.MANAGER and db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == prop.id,
        PropertyAssignment.user_id == actor.id,
        PropertyAssignment.role == UserRole.MANAGER,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first() is None:
        raise HTTPException(403, "Current property manager assignment required")
    return wo, prop


def _purchase(db: Session, actor: User, order_id: int, *, write: bool):
    if order_id < 1:
        raise HTTPException(422, "Invalid material order")
    row = db.query(Order).filter(
        Order.id == order_id, Order.organization_id == actor.organization_id,
    ).first()
    if row is None:
        raise HTTPException(404, "Material order not found")
    wo, prop = _work(db, actor, row.work_order_id, write=write)
    if row.property_id != prop.id or wo.property_id != row.property_id:
        raise HTTPException(409, "Material order location mismatch")
    if db.query(Vendor.id).filter(
        Vendor.id == row.vendor_id, Vendor.organization_id == row.organization_id,
    ).first() is None:
        raise HTTPException(409, "Material supplier company binding mismatch")
    for user_id in (row.requested_by_id, row.reviewed_by_id):
        if user_id is not None and db.query(User.id).filter(
            User.id == user_id, User.organization_id == row.organization_id,
        ).first() is None:
            raise HTTPException(409, "Material approval/requester binding mismatch")
    if write:
        row = db.query(Order).populate_existing().filter(Order.id == row.id).with_for_update().one()
    _assert_original_approval_evidence(db, row)
    return row


def _net(db: Session, row: Order) -> int:
    quantities = db.query(Movement.organization_id, Movement.delta_qty).filter(
        Movement.order_id == row.id,
    ).all()
    if any(org != row.organization_id for org, _ in quantities):
        raise HTTPException(409, "Foreign-company stock movement binding detected")
    return sum(int(qty) for _, qty in quantities)


def _issues(db: Session, row: Order) -> list[Issue]:
    """Validate each issued unit and every immutable source/actor/audit binding."""
    items = db.query(Issue).filter(Issue.material_order_id == row.id).order_by(
        Issue.id.asc()).limit(201).all()
    if len(items) > 200:
        raise HTTPException(409, "Material usage history limit reached")
    if items and row.status != "APPROVED":
        raise HTTPException(409, "Unapproved stock issue integrity violation")
    origins = {item.id: item for item in items if item.delta_qty > 0}
    reversals = set()
    for item in items:
        if item.organization_id != row.organization_id:
            raise HTTPException(409, "Cross-company stock issue binding detected")
        actor = db.query(User.id).filter(
            User.id == item.issued_by_id, User.organization_id == row.organization_id,
        ).first()
        target = db.query(WorkOrder).filter(WorkOrder.id == item.target_work_order_id).first()
        if (actor is None or target is None or target.property_id != row.property_id
                or db.query(Unit.id).filter(
                    Unit.id == target.unit_id, Unit.property_id == row.property_id,
                ).first() is None):
            raise HTTPException(409, "Stock issue target or actor binding invalid")
        if item.delta_qty < 0:
            source = origins.get(item.reverses_id)
            if (source is None or source.delta_qty != -item.delta_qty
                    or source.target_work_order_id != item.target_work_order_id
                    or source.id >= item.id
                    or item.reverses_id in reversals):
                raise HTTPException(409, "Stock issue reversal integrity violation")
            reversals.add(item.reverses_id)
        elif item.reverses_id is not None:
            raise HTTPException(409, "Original stock issue references a reversal")
        audit_action = "stock_issue_reversed" if item.delta_qty < 0 else "stock_issued_to_work_order"
        audit = db.query(AuditLog).filter(
            AuditLog.organization_id == row.organization_id,
            AuditLog.entity_type == "maintenance_material_issue",
            AuditLog.entity_id == item.id, AuditLog.action == audit_action,
        ).one_or_none()
        try:
            details = json.loads(audit.new_value or "{}") if audit else {}
        except (ValueError, TypeError) as exc:
            raise HTTPException(409, "Stock issue audit is corrupt") from exc
        if (audit is None or audit.user_id != item.issued_by_id
                or details.get("material_order_id") != row.id
                or details.get("target_work_order_id") != item.target_work_order_id
                or details.get("property_id") != row.property_id
                or details.get("sku") != row.sku
                or details.get("unit_cost_cents") != row.unit_cost_cents
                or details.get("reference") != item.reference
                or details.get("delta_qty") != item.delta_qty
                or details.get("reverses_id") != item.reverses_id
                or details.get("reason") != item.reason):
            raise HTTPException(409, "Stock issue immutable audit binding mismatch")
    used = sum(item.delta_qty for item in items)
    if used < 0 or used > _net(db, row):
        raise HTTPException(409, "Physical stock conservation violation")
    return items


def _variances(db: Session, row: Order) -> list[dict]:
    """Reconcile immutable physical shortfall requests/decisions/restorations.

    An unapproved discrepancy never silently retires stock. Approved shortage
    reduces available physical units; a separate independently confirmed
    restoration reinstates the same units without changing original records.
    """
    requests = db.query(Variance).filter(Variance.material_order_id == row.id
        ).order_by(Variance.id.asc()).limit(201).all()
    if len(requests)>200:
        raise HTTPException(409,"Physical discrepancy history limit reached")
    accepted=0
    records=[]
    for request in requests:
        if request.organization_id != row.organization_id:
            raise HTTPException(409,"Cross-company physical discrepancy evidence")
        witness = db.query(User.id).filter(
            User.id==request.reported_by_id, User.organization_id==row.organization_id).first()
        decision=db.query(VarianceDecision).filter_by(variance_id=request.id).one_or_none()
        recovery=db.query(VarianceRestore).filter_by(variance_id=request.id).one_or_none()
        if witness is None:
            raise HTTPException(409,"Physical discrepancy witness binding invalid")
        if decision is not None:
            reviewer=db.query(User.id).filter(User.id==decision.reviewed_by_id,
                User.organization_id==row.organization_id).first()
            if (decision.organization_id!=row.organization_id or reviewer is None
                    or decision.reviewed_by_id==request.reported_by_id
                    or decision.approved not in (0,1)):
                raise HTTPException(409,"Discrepancy independent review binding invalid")
        if recovery is not None:
            restorer=db.query(User.id).filter(User.id==recovery.restored_by_id,
                User.organization_id==row.organization_id).first()
            if (decision is None or decision.approved != 1
                    or restorer is None or recovery.organization_id!=row.organization_id
                    or recovery.restored_by_id in (request.reported_by_id,decision.reviewed_by_id)):
                raise HTTPException(409,"Discrepancy recovery testimony invalid")
        history = [
            ("physical_variance_requested", request.id, request.reported_by_id,
                {"material_order_id":row.id,"request_key":request.request_key,
                 "quantity":request.quantity,"reason":request.reason}),
        ]
        if decision is not None:
            history.append(("physical_variance_reviewed",decision.id,decision.reviewed_by_id,
                {"variance_id":request.id,"approved":bool(decision.approved),
                 "reason":decision.reason}))
        if recovery is not None:
            history.append(("physical_variance_restored",recovery.id,recovery.restored_by_id,
                {"variance_id":request.id,"quantity":request.quantity,"reason":recovery.reason}))
        for action,entity_id,actor_id,payload in history:
            audit=db.query(AuditLog).filter(
                AuditLog.organization_id==row.organization_id,
                AuditLog.entity_type=="maintenance_material_variance",
                AuditLog.entity_id==entity_id,AuditLog.action==action,
            ).one_or_none()
            try:
                actual=json.loads(audit.new_value or "{}") if audit else {}
            except (TypeError,ValueError) as ex:
                raise HTTPException(409,"Physical discrepancy audit parse failure") from ex
            if audit is None or audit.user_id != actor_id or any(actual.get(k)!=v for k,v in payload.items()):
                raise HTTPException(409,"Physical discrepancy immutable audit mismatch")
        open_loss=request.quantity if decision is not None and decision.approved==1 and recovery is None else 0
        accepted+=open_loss
        records.append({
            "id":request.id,"request_key":request.request_key,"quantity":request.quantity,
            "reason":request.reason,"reported_by_id":request.reported_by_id,
            "status":"RESTORED" if recovery else (
                "REQUESTED" if decision is None else ("APPROVED" if decision.approved else "DENIED")),
            "reviewed_by_id":decision.reviewed_by_id if decision else None,
            "review_reason":decision.reason if decision else None,
            "restored_by_id":recovery.restored_by_id if recovery else None,
            "restore_reason":recovery.reason if recovery else None,
        })
    if accepted>_net(db,row)-sum(item.delta_qty for item in _issues(db,row)):
        raise HTTPException(409,"Physical discrepancy exceeds unallocated stock")
    return records


def _loss_qty(db: Session, row: Order) -> int:
    return sum(item["quantity"] for item in _variances(db,row) if item["status"]=="APPROVED")


def _available(db: Session, row: Order) -> int:
    return _net(db, row) - sum(item.delta_qty for item in _issues(db, row)) - _loss_qty(db,row)


def _issue_out(item: Issue) -> dict:
    return {
        "id": item.id, "material_order_id": item.material_order_id,
        "target_work_order_id": item.target_work_order_id,
        "reference": item.reference, "delta_qty": item.delta_qty,
        "issued_by_id": item.issued_by_id, "reverses_id": item.reverses_id,
        "reason": item.reason, "recorded_at": item.recorded_at,
    }


def _assert_original_approval_evidence(db: Session, row: Order) -> None:
    """Current business fields must still match the immutable request/decision."""
    logs = db.query(AuditLog).filter(
        AuditLog.organization_id == row.organization_id,
        AuditLog.entity_type == "maintenance_material_order",
        AuditLog.entity_id == row.id,
    ).order_by(AuditLog.id.asc()).all()
    requested = [entry for entry in logs if entry.action == "requested"]
    decisions = [entry for entry in logs if entry.action == "reviewed"]
    if len(requested) != 1 or len(decisions) > 1:
        raise HTTPException(409, "Purchase request audit evidence missing or duplicated")
    try:
        origin = json.loads(requested[0].new_value or "{}")
        if (origin.get("work_order_id") != row.work_order_id
                or origin.get("property_id") != row.property_id
                or origin.get("vendor_id") != row.vendor_id
                or origin.get("request_key") != row.request_key
                or origin.get("sku") != row.sku
                or origin.get("quantity") != row.requested_qty
                or origin.get("unit_cost_cents") != row.unit_cost_cents
                or origin.get("reason") != row.reason
                or requested[0].user_id != row.requested_by_id):
            raise ValueError("Original request binding changed")
        if row.status == "REQUESTED":
            if decisions or row.reviewed_by_id is not None:
                raise ValueError("Pending state has decision evidence")
        else:
            if (len(decisions) != 1 or row.reviewed_by_id is None
                    or row.reviewed_by_id == row.requested_by_id
                    or not row.reviewed_at or not row.decision_reason):
                raise ValueError("Independent approval evidence missing")
            decision = json.loads(decisions[0].new_value or "{}")
            if (decision.get("status") != row.status
                    or decision.get("reason") != row.decision_reason
                    or decision.get("reviewer_id") != row.reviewed_by_id
                    or decisions[0].user_id != row.reviewed_by_id):
                raise ValueError("Independent decision binding changed")
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(409, "Material request immutable audit integrity violation") from exc


def _movement(row: Movement) -> dict:
    return {
        "id": row.id, "delta_qty": row.delta_qty, "reference": row.reference,
        "received_by_id": row.received_by_id, "reason": row.reason,
        "reverses_id": row.reverses_id, "recorded_at": row.recorded_at,
    }


def _out(db: Session, row: Order) -> dict:
    _assert_original_approval_evidence(db, row)
    events = db.query(Movement).filter(
        Movement.order_id == row.id,
    ).order_by(Movement.id.asc()).limit(201).all()
    if len(events) > 200:
        raise HTTPException(409, "Manual receiving history limit reached")
    if any(x.organization_id != row.organization_id for x in events):
        raise HTTPException(409, "Foreign-company stock movement binding detected")
    received_by = {x.received_by_id for x in events}
    permitted_users = {id_ for (id_,) in db.query(User.id).filter(
        User.organization_id == row.organization_id,
        User.id.in_(received_by),
    ).all()} if received_by else set()
    if permitted_users != received_by:
        raise HTTPException(409, "Foreign-company movement actor binding detected")
    if sum(x.delta_qty for x in events) < 0 or sum(x.delta_qty for x in events) > row.requested_qty:
        raise HTTPException(409, "Physical receipt quantity integrity violation")
    issues = _issues(db, row)
    issued = sum(item.delta_qty for item in issues)
    discrepancies = _variances(db, row)
    lost = sum(item["quantity"] for item in discrepancies if item["status"]=="APPROVED")
    return {
        "available_stock": sum(event.delta_qty for event in events) - issued - lost,
        "net_issued": issued,
        "net_missing": lost,
        "stock_variances": discrepancies,
        "material_issues": [_issue_out(item) for item in issues],
        "id": row.id, "organization_id": row.organization_id,
        "property_id": row.property_id, "work_order_id": row.work_order_id,
        "vendor_id": row.vendor_id, "request_key": row.request_key, "sku": row.sku, "item_name": row.item_name,
        "requested_qty": row.requested_qty, "unit_cost_cents": row.unit_cost_cents,
        "reason": row.reason, "status": row.status,
        "requested_by_id": row.requested_by_id, "requested_at": row.requested_at,
        "reviewed_by_id": row.reviewed_by_id, "reviewed_at": row.reviewed_at,
        "decision_reason": row.decision_reason,
        "net_received": sum(event.delta_qty for event in events),
        "physical_receipts": [_movement(event) for event in events],
        "vendor_delivery_confirmed": False, "gl_posted": False, "tenant_charged": False,
    }


@router.get("/vendors")
def candidate_vendors(work_order_id: int = Query(ge=1),
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    _work(db, current_user, work_order_id, write=False)
    return [
        {"id": row.id, "company_name": row.company_name}
        for row in db.query(Vendor).filter(
            Vendor.organization_id == current_user.organization_id,
            Vendor.is_active.is_(True), Vendor.deleted_at.is_(None),
        ).order_by(Vendor.company_name.asc(), Vendor.id.asc()).limit(100).all()
    ]


@router.get("/orders")
def list_orders(work_order_id: int | None = Query(default=None, ge=1),
                limit: int = Query(default=50, ge=1, le=100),
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    _staff(db, current_user)
    query = db.query(Order).filter(Order.organization_id == current_user.organization_id)
    if work_order_id is not None:
        _work(db, current_user, work_order_id, write=False)
        query = query.filter(Order.work_order_id == work_order_id)
    # Require every real current property scope, even for stale/forged joins.
    if current_user.role == UserRole.MANAGER:
        permitted = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.role == UserRole.MANAGER,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Order.property_id.in_(permitted))
    rows = query.order_by(Order.id.desc()).limit(limit).all()
    return [_out(db, _purchase(db, current_user, row.id, write=False)) for row in rows]


@router.post("/orders", status_code=201)
def create_order(payload: NewOrder, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    wo, prop = _work(db, current_user, payload.work_order_id, write=True)
    vendor = db.query(Vendor.id).filter(
        Vendor.id == payload.vendor_id,
        Vendor.organization_id == current_user.organization_id,
        Vendor.is_active.is_(True), Vendor.deleted_at.is_(None),
    ).first()
    if vendor is None:
        raise HTTPException(404, "Eligible organization vendor not found")
    existing = db.query(Order).filter(
        Order.organization_id == current_user.organization_id,
        Order.request_key == payload.request_key,
    ).first()
    if existing is not None:
        if (existing.work_order_id == wo.id and existing.property_id == prop.id
                and existing.vendor_id == payload.vendor_id
                and existing.sku == payload.sku.upper()
                and existing.item_name == payload.item_name.strip()
                and existing.requested_qty == payload.quantity
                and existing.unit_cost_cents == payload.unit_cost_cents
                and existing.reason == payload.reason.strip()
                and existing.requested_by_id == current_user.id):
            return _out(db, existing)
        raise HTTPException(409, "Conflicting purchase request retry")
    row = Order(
        organization_id=current_user.organization_id, property_id=prop.id,
        work_order_id=wo.id, vendor_id=payload.vendor_id,
        request_key=payload.request_key, sku=payload.sku.upper(), item_name=payload.item_name.strip(),
        requested_qty=payload.quantity, unit_cost_cents=payload.unit_cost_cents,
        reason=payload.reason.strip(), status="REQUESTED",
        requested_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        # A parallel writer on another property may win the unique request
        # key. Fail closed rather than fabricate duplicate procurement.
        raise HTTPException(409, "Concurrent purchase request key conflict; reload before retrying") from exc
    append_audit_log(
        db, organization_id=current_user.organization_id, user_id=current_user.id,
        entity_type="maintenance_material_order", entity_id=row.id, action="requested",
        new_value={"work_order_id": wo.id, "property_id": prop.id,
                   "vendor_id": row.vendor_id, "request_key": row.request_key, "sku": row.sku,
                   "quantity": row.requested_qty, "unit_cost_cents": row.unit_cost_cents,
                   "reason": row.reason, "external_order_sent": False},
    )
    db.commit()
    return _out(db, row)


@router.post("/orders/{order_id}/decision")
def decide_order(order_id: int, payload: Decision,
                 db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    row = _purchase(db, current_user, order_id, write=True)
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(403, "Owner/Admin independent review required")
    if row.requested_by_id == current_user.id:
        raise HTTPException(403, "Requester cannot independently approve or deny")
    choice = "APPROVED" if payload.approved else "DENIED"
    if row.status != "REQUESTED":
        if row.status == choice and row.decision_reason == payload.reason.strip():
            return _out(db, row)
        raise HTTPException(409, "Purchase decision is final")
    row.status = choice
    row.reviewed_by_id = current_user.id
    row.reviewed_at = datetime.utcnow()
    row.decision_reason = payload.reason.strip()
    append_audit_log(
        db, organization_id=row.organization_id, user_id=current_user.id,
        entity_type="maintenance_material_order", entity_id=row.id,
        action="reviewed", old_value={"status": "REQUESTED"},
        new_value={"status": choice, "reason": row.decision_reason,
                   "reviewer_id": current_user.id, "payables_posted": False},
    )
    db.commit()
    return _out(db, row)


@router.post("/orders/{order_id}/receive", status_code=201)
def receive_materials(order_id: int, payload: Receipt,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    row = _purchase(db, current_user, order_id, write=True)
    if row.status != "APPROVED":
        raise HTTPException(409, "Purchase must be independently approved")
    source = db.query(Vendor.id).filter(
        Vendor.id == row.vendor_id, Vendor.organization_id == row.organization_id,
        Vendor.is_active.is_(True), Vendor.deleted_at.is_(None),
    ).first()
    if source is None:
        raise HTTPException(409, "Vendor no longer eligible for new receiving")
    reference = payload.reference.strip()
    if reference.upper().startswith("REV-"):
        raise HTTPException(422, "REV- receipt references are reserved for audited corrections")
    replay = db.query(Movement).filter_by(order_id=row.id, reference=reference).first()
    if replay is not None:
        if replay.delta_qty == payload.quantity and replay.reason == payload.notes.strip() and replay.reverses_id is None:
            return _out(db, row)
        raise HTTPException(409, "Conflicting receipt reference")
    if _net(db, row) + payload.quantity > row.requested_qty:
        raise HTTPException(409, "Receiving exceeds approved quantity")
    if db.query(Movement.id).filter(Movement.order_id == row.id).count() >= 200:
        raise HTTPException(409, "Manual receiving history limit reached")
    receipt = Movement(
        organization_id=row.organization_id, order_id=row.id,
        reference=reference, delta_qty=payload.quantity,
        received_by_id=current_user.id, reason=payload.notes.strip(),
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent receipt reference conflict; reload before retrying") from exc
    append_audit_log(
        db, organization_id=row.organization_id, user_id=current_user.id,
        entity_type="maintenance_material_movement", entity_id=receipt.id,
        action="physical_receipt_attested",
        new_value={"order_id": row.id, "property_id": row.property_id,
                   "sku": row.sku, "quantity": payload.quantity,
                   "reference": reference, "supplier_delivery_confirmed": False,
                   "financial_posted": False, "reason": receipt.reason},
    )
    db.commit()
    return _out(db, row)


@router.post("/orders/{order_id}/movements/{movement_id}/reverse")
def reverse_receipt(order_id: int, movement_id: int, payload: Correction,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    row = _purchase(db, current_user, order_id, write=True)
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(403, "Owner/Admin physical receipt correction required")
    original = db.query(Movement).filter(
        Movement.id == movement_id, Movement.order_id == row.id,
        Movement.organization_id == row.organization_id, Movement.delta_qty > 0,
    ).first()
    if original is None:
        raise HTTPException(404, "Original receipt not found")
    if original.received_by_id == current_user.id:
        raise HTTPException(403, "Receiver cannot independently reverse own receipt")
    previous = db.query(Movement).filter(Movement.reverses_id == original.id).first()
    if previous is not None:
        if (previous.reason == payload.reason.strip()
                and previous.received_by_id == current_user.id):
            return _out(db, row)
        raise HTTPException(409, "Original receipt already reversed by another decision")
    if _net(db, row) - original.delta_qty < sum(
        event.delta_qty for event in _issues(db, row)
    ) + _loss_qty(db,row):
        raise HTTPException(409, "Receipt reversal would consume allocated stock")
    if db.query(Movement.id).filter(Movement.order_id == row.id).count() >= 200:
        raise HTTPException(409, "Manual receiving history limit reached")
    reversal = Movement(
        organization_id=row.organization_id, order_id=row.id,
        reference="REV-" + str(original.id), delta_qty=-original.delta_qty,
        received_by_id=current_user.id, reverses_id=original.id,
        reason=payload.reason.strip(),
    )
    db.add(reversal)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent physical reversal; reload before retrying") from exc
    append_audit_log(
        db, organization_id=row.organization_id, user_id=current_user.id,
        entity_type="maintenance_material_movement", entity_id=reversal.id,
        action="physical_receipt_reversed",
        new_value={"order_id": row.id, "original_movement_id": original.id,
                   "property_id": row.property_id, "sku": row.sku,
                   "quantity_delta": reversal.delta_qty, "reason": reversal.reason,
                   "financial_posted": False},
    )
    db.commit()
    return _out(db, row)




@router.post("/orders/{order_id}/issue", status_code=201)
def issue_materials(order_id: int, payload: IssueStock,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Record actual physical usage against a specific authorized work order."""
    row = _purchase(db, current_user, order_id, write=True)
    if row.status != "APPROVED":
        raise HTTPException(409, "Material source must have independent approval")
    target, property_row = _work(db, current_user, payload.target_work_order_id, write=True)
    if property_row.id != row.property_id or target.property_id != row.property_id:
        raise HTTPException(409, "Material stock cannot cross properties")
    reference = payload.reference.strip()
    if reference.upper().startswith("REV-USE-"):
        raise HTTPException(422, "REV-USE references are reserved for independent reversal")
    existing = db.query(Issue).filter_by(material_order_id=row.id, reference=reference).first()
    if existing is not None:
        if (existing.delta_qty == payload.quantity
                and existing.target_work_order_id == target.id
                and existing.reason == payload.notes.strip()
                and existing.issued_by_id == current_user.id
                and existing.reverses_id is None):
            return _out(db, row)
        raise HTTPException(409, "Conflicting material usage reference")
    if len(_issues(db, row)) >= 200:
        raise HTTPException(409, "Material usage history limit reached")
    if _available(db, row) < payload.quantity:
        raise HTTPException(409, "Insufficient unallocated physical stock")
    issue = Issue(
        organization_id=row.organization_id, material_order_id=row.id,
        target_work_order_id=target.id, reference=reference,
        delta_qty=payload.quantity, issued_by_id=current_user.id,
        reason=payload.notes.strip(),
    )
    db.add(issue)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent material issue; reload before retrying") from exc
    append_audit_log(
        db, organization_id=row.organization_id, user_id=current_user.id,
        entity_type="maintenance_material_issue", entity_id=issue.id,
        action="stock_issued_to_work_order",
        new_value={"material_order_id": row.id, "property_id": row.property_id,
                   "target_work_order_id": target.id, "reference": reference,
                   "delta_qty": payload.quantity, "reverses_id": None,
                   "reason": issue.reason, "sku": row.sku,
                   "unit_cost_cents": row.unit_cost_cents,
                   "gl_posted": False, "tenant_charged": False},
    )
    db.commit()
    return _out(db, row)


@router.post("/orders/{order_id}/issues/{issue_id}/reverse")
def reverse_material_issue(order_id: int, issue_id: int, payload: Correction,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    row = _purchase(db, current_user, order_id, write=True)
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(403, "Independent Owner/Admin issue reversal required")
    previous = db.query(Issue).filter(
        Issue.material_order_id == row.id, Issue.id == issue_id,
        Issue.organization_id == row.organization_id, Issue.delta_qty > 0,
    ).first()
    if previous is None:
        raise HTTPException(404, "Original physical stock issue not found")
    if previous.issued_by_id == current_user.id:
        raise HTTPException(403, "Issuer cannot reverse own stock issue")
    existing = db.query(Issue).filter_by(reverses_id=previous.id).first()
    if existing is not None:
        if (existing.reason == payload.reason.strip()
                and existing.issued_by_id == current_user.id):
            return _out(db, row)
        raise HTTPException(409, "Stock issue was already reversed by another decision")
    if len(_issues(db, row)) >= 200:
        raise HTTPException(409, "Material usage history limit reached")
    reversal = Issue(
        organization_id=row.organization_id, material_order_id=row.id,
        target_work_order_id=previous.target_work_order_id,
        reference="REV-USE-" + str(previous.id),
        delta_qty=-previous.delta_qty, issued_by_id=current_user.id,
        reverses_id=previous.id, reason=payload.reason.strip(),
    )
    db.add(reversal)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent issue reversal; reload before retrying") from exc
    append_audit_log(
        db, organization_id=row.organization_id, user_id=current_user.id,
        entity_type="maintenance_material_issue", entity_id=reversal.id,
        action="stock_issue_reversed",
        new_value={"material_order_id": row.id, "property_id": row.property_id,
                   "target_work_order_id": reversal.target_work_order_id,
                   "reference": reversal.reference, "delta_qty": reversal.delta_qty,
                   "reverses_id": previous.id, "reason": reversal.reason,
                   "sku": row.sku, "unit_cost_cents": row.unit_cost_cents,
                   "gl_posted": False, "tenant_charged": False},
    )
    db.commit()
    return _out(db, row)




@router.post("/orders/{order_id}/variances", status_code=201)
def report_stock_variance(order_id: int, payload: StockVarianceInput,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    row=_purchase(db,current_user,order_id,write=True)
    if row.status!="APPROVED":
        raise HTTPException(409,"Only independently approved physical stock can be counted")
    existing=db.query(Variance).filter(
        Variance.organization_id==row.organization_id,Variance.request_key==payload.request_key).first()
    if existing is not None:
        if (existing.material_order_id==row.id and existing.quantity==payload.quantity
                and existing.reason==payload.reason.strip() and existing.reported_by_id==current_user.id):
            return _out(db,row)
        raise HTTPException(409,"Conflicting discrepancy request key")
    if _available(db,row)<payload.quantity:
        raise HTTPException(409,"Cannot propose a loss greater than currently available stock")
    if len(_variances(db,row))>=200:
        raise HTTPException(409,"Physical discrepancy history limit reached")
    event=Variance(
        organization_id=row.organization_id,material_order_id=row.id,
        request_key=payload.request_key,quantity=payload.quantity,
        reason=payload.reason.strip(),reported_by_id=current_user.id)
    db.add(event)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,"Concurrent discrepancy request; reload before retry") from exc
    append_audit_log(db,organization_id=row.organization_id,user_id=current_user.id,
        entity_type="maintenance_material_variance",entity_id=event.id,
        action="physical_variance_requested",
        new_value={"material_order_id":row.id,"property_id":row.property_id,
            "request_key":event.request_key,"quantity":event.quantity,"reason":event.reason,
            "financial_posted":False,"tenant_charged":False})
    db.commit()
    return _out(db,row)


@router.post("/orders/{order_id}/variances/{variance_id}/decision")
def review_stock_variance(order_id: int,variance_id:int,payload:Decision,
                          db: Session=Depends(get_db),
                          current_user:User=Depends(get_current_user)):
    row=_purchase(db,current_user,order_id,write=True)
    if current_user.role not in (UserRole.ADMIN,UserRole.OWNER):
        raise HTTPException(403,"Independent Owner/Admin stock review required")
    request=db.query(Variance).filter(Variance.id==variance_id,
        Variance.material_order_id==row.id,Variance.organization_id==row.organization_id).first()
    if request is None: raise HTTPException(404,"Physical discrepancy not found")
    if request.reported_by_id==current_user.id:
        raise HTTPException(403,"Physical discrepancy witness cannot self-approve")
    previous=db.query(VarianceDecision).filter_by(variance_id=request.id).first()
    if previous is not None:
        if (previous.reviewed_by_id==current_user.id and
                bool(previous.approved)==payload.approved and previous.reason==payload.reason.strip()):
            return _out(db,row)
        raise HTTPException(409,"Original discrepancy already independently reviewed")
    if payload.approved and _available(db,row)<request.quantity:
        raise HTTPException(409,"Physical stock consumed since discrepancy report; recount required")
    event=VarianceDecision(organization_id=row.organization_id,variance_id=request.id,
        approved=int(payload.approved),reason=payload.reason.strip(),reviewed_by_id=current_user.id)
    db.add(event)
    try: db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,"Concurrent stock decision; reload before retry") from exc
    append_audit_log(db,organization_id=row.organization_id,user_id=current_user.id,
        entity_type="maintenance_material_variance",entity_id=event.id,
        action="physical_variance_reviewed",
        new_value={"variance_id":request.id,"property_id":row.property_id,
            "approved":bool(event.approved),"reason":event.reason,
            "financial_posted":False,"tenant_charged":False})
    db.commit()
    return _out(db,row)


@router.post("/orders/{order_id}/variances/{variance_id}/restore")
def restore_stock_variance(order_id:int,variance_id:int,payload:Correction,
                           db:Session=Depends(get_db),
                           current_user:User=Depends(get_current_user)):
    row=_purchase(db,current_user,order_id,write=True)
    if current_user.role not in (UserRole.ADMIN,UserRole.OWNER):
        raise HTTPException(403,"Independent Owner/Admin physical recount required")
    request=db.query(Variance).filter(Variance.id==variance_id,
        Variance.material_order_id==row.id,Variance.organization_id==row.organization_id).first()
    if request is None: raise HTTPException(404,"Physical discrepancy not found")
    decision=db.query(VarianceDecision).filter_by(variance_id=request.id).first()
    if decision is None or decision.approved!=1:
        raise HTTPException(409,"Only an independently approved shortage can be restored")
    if current_user.id in (request.reported_by_id,decision.reviewed_by_id):
        raise HTTPException(403,"Original witness or reviewer cannot certify recovery")
    existing=db.query(VarianceRestore).filter_by(variance_id=request.id).first()
    if existing is not None:
        if existing.restored_by_id==current_user.id and existing.reason==payload.reason.strip():
            return _out(db,row)
        raise HTTPException(409,"Shortage has already been corrected independently")
    event=VarianceRestore(organization_id=row.organization_id,variance_id=request.id,
        reason=payload.reason.strip(),restored_by_id=current_user.id)
    db.add(event)
    try: db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,"Concurrent physical recovery; reload before retry") from exc
    append_audit_log(db,organization_id=row.organization_id,user_id=current_user.id,
        entity_type="maintenance_material_variance",entity_id=event.id,
        action="physical_variance_restored",
        new_value={"variance_id":request.id,"quantity":request.quantity,
            "property_id":row.property_id,"reason":event.reason,
            "financial_posted":False,"tenant_charged":False})
    db.commit()
    return _out(db,row)


@router.get("/stock")
def stock_at_property(property_id: int = Query(ge=1),
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    _staff(db, current_user)
    prop = db.query(Property).filter(
        Property.id == property_id, Property.organization_id == current_user.organization_id,
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found")
    if current_user.role == UserRole.MANAGER and db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == property_id,
        PropertyAssignment.user_id == current_user.id,
        PropertyAssignment.role == UserRole.MANAGER,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first() is None:
        raise HTTPException(403, "Current property manager assignment required")
    foreign_bind = db.query(Movement.id).join(
        Order, Movement.order_id == Order.id,
    ).filter(
        Order.organization_id == current_user.organization_id,
        Order.property_id == property_id,
        Movement.organization_id != current_user.organization_id,
    ).first()
    if foreign_bind is not None:
        raise HTTPException(409, "Cross-organization material movement detected")
    counts = db.query(Order.sku, func.min(Order.item_name), func.sum(Movement.delta_qty)).join(
        Movement, Movement.order_id == Order.id,
    ).filter(
        Order.organization_id == current_user.organization_id,
        Movement.organization_id == current_user.organization_id,
        Order.property_id == property_id, Order.status == "APPROVED",
    ).group_by(Order.sku).all()
    if any(int(total) < 0 for _, _, total in counts):
        raise HTTPException(409, "Physical stock count integrity violation")
    by_sku = {sku: {"sku": sku, "item_name": name, "quantity": int(total)}
              for sku, name, total in counts}
    # The property lock used in all issue/receiving writes protects this
    # physical count against simultaneous source-order allocations.
    issued = db.query(Issue, Order, WorkOrder).select_from(Issue).join(
        Order, Issue.material_order_id == Order.id,
    ).outerjoin(
        WorkOrder, Issue.target_work_order_id == WorkOrder.id,
    ).filter(
        Order.organization_id == current_user.organization_id,
        Order.property_id == property_id,
    ).all()
    for event, source, target in issued:
        if (event.organization_id != source.organization_id
                or target is None or target.property_id != property_id
                or source.status != "APPROVED"):
            raise HTTPException(409, "Property stock issue binding integrity violation")
    # Validate immutable audit and reversal structures before trusting totals.
    for source_id in {source.id for _, source, _ in issued}:
        source = next(order for _, order, _ in issued if order.id == source_id)
        _issues(db, source)
    for event, source, _ in issued:
        if source.sku not in by_sku:
            raise HTTPException(409, "Stock issue has no received source")
        by_sku[source.sku]["quantity"] -= event.delta_qty
    all_sources=db.query(Order).filter(
        Order.organization_id==current_user.organization_id,
        Order.property_id==property_id,Order.status=="APPROVED").all()
    for source in all_sources:
        loss=_loss_qty(db,source)
        if loss:
            if source.sku not in by_sku:
                raise HTTPException(409,"Approved shortage has no original receipt")
            by_sku[source.sku]["quantity"]-=loss
    if any(row["quantity"] < 0 for row in by_sku.values()):
        raise HTTPException(409, "Property stock physical conservation violation")
    return [row for row in sorted(by_sku.values(), key=lambda item: item["sku"])
            if row["quantity"] > 0]
