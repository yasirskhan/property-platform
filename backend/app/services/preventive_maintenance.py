"""Staff-authorized preventive maintenance with durable, idempotent manual due generation."""
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.preventive_maintenance import PreventiveMaintenanceSchedule as Schedule, PreventiveMaintenanceOccurrence as Occurrence
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderUpdate
from app.routers.properties import check_property_access
from app.services.audit import append_audit_log

def _scope(db: Session, actor: User, unit_id: int):
    if not actor.is_active or actor.deleted_at is not None or actor.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Preventive maintenance requires authorized staff")
    unit = db.query(Unit).join(Property, Property.id == Unit.property_id).filter(
        Unit.id == unit_id, Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        Property.organization_id == actor.organization_id, Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).first()
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not available")
    check_property_access(db, actor, unit.property_id)
    return unit

def _schedule(db: Session, actor: User, schedule_id: int):
    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id, Schedule.organization_id == actor.organization_id,
    ).first()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    _scope(db, actor, schedule.unit_id)
    if schedule.property_id != db.query(Unit.property_id).filter(Unit.id == schedule.unit_id).scalar():
        raise HTTPException(status_code=404, detail="Schedule parent mismatch")
    return schedule

def create_schedule(db: Session, actor: User, *, unit_id: int, title: str,
                    description: str, interval_days: int, next_due_date: date):
    unit = _scope(db, actor, unit_id)
    if interval_days < 1 or interval_days > 3650:
        raise HTTPException(status_code=422, detail="Invalid schedule interval")
    if next_due_date < date.today():
        raise HTTPException(status_code=422, detail="Start date must not be historical")
    row = Schedule(organization_id=actor.organization_id, property_id=unit.property_id,
        unit_id=unit.id, title=title, description=description,
        interval_days=interval_days, next_due_date=next_due_date,
        created_by_id=actor.id, active=True)
    db.add(row)
    db.flush()
    append_audit_log(db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
        organization_id=actor.organization_id, user_id=actor.id, action="created",
        new_value={"unit_id":unit.id, "property_id":unit.property_id, "interval_days":interval_days,
                   "next_due_date":next_due_date.isoformat(), "title":title})
    db.commit()
    db.refresh(row)
    return row

def list_schedules(db: Session, actor: User):
    if not actor.is_active or actor.deleted_at is not None or actor.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Preventive maintenance requires authorized staff")
    items = db.query(Schedule).filter(Schedule.organization_id == actor.organization_id).order_by(Schedule.id.desc()).all()
    visible = []
    for item in items:
        try:
            _schedule(db, actor, item.id)
        except HTTPException:
            continue
        visible.append(item)
    return visible

def set_active(db: Session, actor: User, schedule_id: int, active: bool):
    row = _schedule(db, actor, schedule_id)
    old = row.active
    if old != active:
        row.active = active
        row.updated_at = __import__("datetime").datetime.utcnow()
        append_audit_log(db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
            organization_id=actor.organization_id, user_id=actor.id, action="active_changed",
            old_value={"active":old}, new_value={"active":active})
        db.commit()
        db.refresh(row)
    return row

def generate_due(db: Session, actor: User, schedule_id: int, *, as_of: date):
    """Generate ONE due occurrence under row lock; retries return the same order."""
    row = _schedule(db, actor, schedule_id)
    if as_of > date.today():
        raise HTTPException(status_code=422, detail="Cannot create future occurrences")
    if not row.active:
        raise HTTPException(status_code=409, detail="Schedule is paused")
    # Lock the parent schedule to serialize two concurrent workers using PostgreSQL.
    row = db.query(Schedule).filter(Schedule.id == row.id).with_for_update().one()
    if not row.active:
        raise HTTPException(status_code=409, detail="Schedule is paused")
    _scope(db, actor, row.unit_id)  # Revalidate under the lock before any write.
    if row.next_due_date > as_of:
        previous = db.query(Occurrence).filter(Occurrence.schedule_id == row.id,
            Occurrence.due_date <= as_of).order_by(Occurrence.due_date.desc()).first()
        if previous:
            return db.query(WorkOrder).filter(WorkOrder.id == previous.work_order_id).one(), False
        raise HTTPException(status_code=409, detail="No occurrence is due")
    due = row.next_due_date
    existing = db.query(Occurrence).filter_by(schedule_id=row.id, due_date=due).first()
    if existing:
        return db.query(WorkOrder).filter(WorkOrder.id == existing.work_order_id).one(), False
    unit = _scope(db, actor, row.unit_id)
    wo = WorkOrder(
        property_id=unit.property_id, unit_id=unit.id, tenant_id=None,
        request_origin="staff", requested_by_user_id=actor.id,
        title=row.title, description=row.description, status=WorkOrderStatus.SUBMITTED,
        permission_to_enter=False)
    db.add(wo)
    db.flush()
    db.add(WorkOrderUpdate(work_order_id=wo.id, user_id=actor.id,
                           to_status=WorkOrderStatus.SUBMITTED, message="Preventive schedule occurrence"))
    db.add(Occurrence(organization_id=actor.organization_id, schedule_id=row.id,
        due_date=due, work_order_id=wo.id))
    row.next_due_date = due + timedelta(days=row.interval_days)
    row.updated_at = __import__("datetime").datetime.utcnow()
    append_audit_log(db, entity_type="preventive_maintenance_occurrence", entity_id=row.id,
        organization_id=actor.organization_id, user_id=actor.id, action="generated",
        new_value={"schedule_id":row.id, "due_date":due.isoformat(), "work_order_id":wo.id})
    append_audit_log(db, entity_type="work_order", entity_id=wo.id,
        organization_id=actor.organization_id, user_id=actor.id, action="status_transition",
        new_value={"status":"submitted","request_origin":"staff","requested_by_user_id":actor.id,
                   "preventive_schedule_id":row.id,"occurrence_date":due.isoformat()})
    db.commit()
    db.refresh(wo)
    return wo, True


def list_occurrences(db: Session, actor: User, schedule_id: int,
                     *, limit: int = 100, offset: int = 0):
    """Authorized durable evidence for every generated occurrence."""
    _schedule(db, actor, schedule_id)
    schedule = _schedule(db, actor, schedule_id)
    # Join through the real work-order unit/property, not untrusted historical
    # label columns: a corrupted occurrence must never expose foreign work IDs.
    return db.query(Occurrence).join(
        WorkOrder, WorkOrder.id == Occurrence.work_order_id,
    ).join(
        Unit, Unit.id == WorkOrder.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).filter(
        Occurrence.organization_id == actor.organization_id,
        Occurrence.schedule_id == schedule_id,
        WorkOrder.unit_id == schedule.unit_id,
        WorkOrder.property_id == schedule.property_id,
        Property.id == schedule.property_id,
        Property.organization_id == actor.organization_id,
    ).order_by(Occurrence.due_date.desc(), Occurrence.id.desc()).offset(offset).limit(limit).all()
