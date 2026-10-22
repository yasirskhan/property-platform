"""Staff procurement approval and attested physical receiving, WITHOUT payables."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.maintenance_material import MaintenanceMaterialOrder as Order, MaintenanceMaterialMovement as Movement
from app.models.property import Property, PropertyAssignment
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
    if write:
        row = db.query(Order).populate_existing().filter(Order.id == row.id).with_for_update().one()
    return row


def _net(db: Session, row: Order) -> int:
    quantities = db.query(Movement.organization_id, Movement.delta_qty).filter(
        Movement.order_id == row.id,
    ).all()
    if any(org != row.organization_id for org, _ in quantities):
        raise HTTPException(409, "Foreign-company stock movement binding detected")
    return sum(int(qty) for _, qty in quantities)


def _movement(row: Movement) -> dict:
    return {
        "id": row.id, "delta_qty": row.delta_qty, "reference": row.reference,
        "received_by_id": row.received_by_id, "reason": row.reason,
        "reverses_id": row.reverses_id, "recorded_at": row.recorded_at,
    }


def _out(db: Session, row: Order) -> dict:
    events = db.query(Movement).filter(
        Movement.order_id == row.id,
    ).order_by(Movement.id.asc()).limit(201).all()
    if len(events) > 200:
        raise HTTPException(409, "Manual receiving history limit reached")
    if any(x.organization_id != row.organization_id for x in events):
        raise HTTPException(409, "Foreign-company stock movement binding detected")
    return {
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
    db.flush()
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
    db.flush()
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
        if previous.reason == payload.reason.strip():
            return _out(db, row)
        raise HTTPException(409, "Original receipt already reversed")
    if _net(db, row) < original.delta_qty:
        raise HTTPException(409, "Stock cannot become negative")
    if db.query(Movement.id).filter(Movement.order_id == row.id).count() >= 200:
        raise HTTPException(409, "Manual receiving history limit reached")
    reversal = Movement(
        organization_id=row.organization_id, order_id=row.id,
        reference="REV-" + str(original.id), delta_qty=-original.delta_qty,
        received_by_id=current_user.id, reverses_id=original.id,
        reason=payload.reason.strip(),
    )
    db.add(reversal)
    db.flush()
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
    counts = db.query(Order.sku, Order.item_name, func.sum(Movement.delta_qty)).join(
        Movement, Movement.order_id == Order.id,
    ).filter(
        Order.organization_id == current_user.organization_id,
        Movement.organization_id == current_user.organization_id,
        Order.property_id == property_id, Order.status == "APPROVED",
    ).group_by(Order.sku, Order.item_name).all()
    return [{"sku": sku, "item_name": name, "quantity": int(total)}
            for sku, name, total in counts if total]
