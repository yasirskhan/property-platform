"""Staff-authorized preventive maintenance with durable, idempotent manual due generation."""
from datetime import date, datetime, timedelta
import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app.models.preventive_maintenance import PreventiveMaintenanceSchedule as Schedule, PreventiveMaintenanceOccurrence as Occurrence
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderUpdate
from app.models.audit_log import AuditLog
from app.routers.properties import check_property_access
from app.services.audit import append_audit_log

_UNSET = object()

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

def read_schedule(db: Session, actor: User, schedule_id: int):
    """Scope historical schedule evidence without requiring active inventory."""
    if not actor.is_active or actor.deleted_at is not None or actor.role not in (
        UserRole.ADMIN, UserRole.MANAGER,
    ):
        raise HTTPException(status_code=403, detail="Preventive maintenance requires authorized staff")
    query = db.query(Schedule).join(Unit, Unit.id == Schedule.unit_id).join(
        Property, Property.id == Unit.property_id,
    ).filter(
        Schedule.id == schedule_id, Schedule.organization_id == actor.organization_id,
        Schedule.property_id == Unit.property_id,
        Property.organization_id == actor.organization_id,
    )
    if actor.role == UserRole.MANAGER:
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    row = query.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return row


def create_schedule(db: Session, actor: User, *, unit_id: int, title: str,
                    description: str, interval_days: int, next_due_date: date, end_date: date | None = None):
    unit = _scope(db, actor, unit_id)
    if interval_days < 1 or interval_days > 3650:
        raise HTTPException(status_code=422, detail="Invalid schedule interval")
    if next_due_date < date.today():
        raise HTTPException(status_code=422, detail="Start date must not be historical")
    if end_date is not None and end_date < next_due_date:
        raise HTTPException(status_code=422, detail="End date cannot precede the first due date")
    row = Schedule(organization_id=actor.organization_id, property_id=unit.property_id,
        unit_id=unit.id, title=title, description=description,
        interval_days=interval_days, next_due_date=next_due_date,
        end_date=end_date, created_by_id=actor.id, active=True)
    db.add(row)
    db.flush()
    append_audit_log(db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
        organization_id=actor.organization_id, user_id=actor.id, action="created",
        new_value={"unit_id":unit.id, "property_id":unit.property_id, "interval_days":interval_days,
                   "next_due_date":next_due_date.isoformat(), "title":title,
                   "end_date":end_date.isoformat() if end_date is not None else None})
    db.commit()
    db.refresh(row)
    return row

def list_schedules(db: Session, actor: User, *, limit: int = 100, offset: int = 0):
    if not actor.is_active or actor.deleted_at is not None or actor.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Preventive maintenance requires authorized staff")
    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail="Invalid schedule pagination")
    query = db.query(Schedule).join(
        Unit, Unit.id == Schedule.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).filter(
        Schedule.organization_id == actor.organization_id,
        Property.organization_id == actor.organization_id,
        Schedule.property_id == Unit.property_id,
    )
    if actor.role == UserRole.MANAGER:
        authorized_properties = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(authorized_properties))
    return query.order_by(Schedule.id.desc()).offset(offset).limit(limit).all()


def set_active(db: Session, actor: User, schedule_id: int, active: bool):
    scoped = _schedule(db, actor, schedule_id)
    # Serialize pause/resume against worker generation and template updates.
    row = db.query(Schedule).populate_existing().filter(
        Schedule.id == scoped.id,
        Schedule.organization_id == actor.organization_id,
    ).with_for_update().one()
    _scope(db, actor, row.unit_id)
    old = row.active
    if old != active:
        row.active = active
        row.updated_at = datetime.utcnow()
        append_audit_log(db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
            organization_id=actor.organization_id, user_id=actor.id, action="active_changed",
            old_value={"active":old}, new_value={"active":active})
        db.commit()
        db.refresh(row)
    return row


def update_settings(db: Session, actor: User, schedule_id: int, *,
                    title: str | None = None, description: str | None = None,
                    interval_days: int | None = None, end_date: date | None | object = _UNSET):
    """Update a paused schedule without rewriting due dates or old work orders."""
    scoped = _schedule(db, actor, schedule_id)
    row = db.query(Schedule).populate_existing().filter(
        Schedule.id == scoped.id, Schedule.organization_id == actor.organization_id,
    ).with_for_update().one()
    _scope(db, actor, row.unit_id)
    if row.active:
        raise HTTPException(status_code=409, detail="Pause schedule before editing")
    requested = {}
    if title is not None:
        title = title.strip()
        if not 3 <= len(title) <= 255:
            raise HTTPException(status_code=422, detail="Invalid title")
        requested["title"] = title
    if description is not None:
        description = description.strip()
        if not 10 <= len(description) <= 2000:
            raise HTTPException(status_code=422, detail="Invalid description")
        requested["description"] = description
    if interval_days is not None:
        if not 1 <= interval_days <= 3650:
            raise HTTPException(status_code=422, detail="Invalid interval")
        requested["interval_days"] = interval_days
    if end_date is not _UNSET:
        if end_date is not None and end_date < date.today():
            raise HTTPException(status_code=422, detail="End date cannot be historical")
        requested["end_date"] = end_date
    if not requested:
        raise HTTPException(status_code=422, detail="Provide a setting to edit")
    changes = {key: (getattr(row, key), value) for key, value in requested.items()
               if getattr(row, key) != value}
    if not changes:
        return row
    for key, (_, value) in changes.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    append_audit_log(
        db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
        organization_id=actor.organization_id, user_id=actor.id,
        action="settings_changed",
        old_value={key: old for key, (old, _) in changes.items()},
        new_value={key: new for key, (_, new) in changes.items()},
    )
    db.commit()
    db.refresh(row)
    return row


def _last_valid_occurrence(db: Session, schedule: Schedule, as_of: date):
    """Fail closed rather than silently skipping the latest corrupted replay."""
    candidate = db.query(Occurrence).filter(
        Occurrence.schedule_id == schedule.id,
        Occurrence.due_date <= as_of,
    ).order_by(Occurrence.due_date.desc(), Occurrence.id.desc()).first()
    if candidate is None:
        return None
    if candidate.organization_id != schedule.organization_id:
        raise HTTPException(status_code=409, detail="Occurrence organization integrity violation")
    order = db.query(WorkOrder).join(
        Unit, Unit.id == WorkOrder.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).filter(
        WorkOrder.id == candidate.work_order_id,
        WorkOrder.unit_id == schedule.unit_id,
        WorkOrder.property_id == schedule.property_id,
        Property.id == schedule.property_id,
        Property.organization_id == schedule.organization_id,
    ).first()
    if order is None:
        raise HTTPException(status_code=409, detail="Occurrence work-order integrity violation")
    # A corrupt pointer may still reference a different order in the same unit.
    # Require the original immutable creation audit to bind this exact order to
    # the schedule and occurrence date, rather than trusting mutable FKs alone.
    creation = db.query(AuditLog).filter(
        AuditLog.organization_id == schedule.organization_id,
        AuditLog.entity_type == "work_order",
        AuditLog.entity_id == order.id,
        AuditLog.action == "status_transition",
    ).order_by(AuditLog.id.asc()).all()
    bound = False
    for record in creation:
        try:
            evidence = json.loads(record.new_value or "null")
        except (ValueError, TypeError):
            continue
        if (
            isinstance(evidence, dict)
            and evidence.get("status") == "submitted"
            and evidence.get("preventive_schedule_id") == schedule.id
            and evidence.get("occurrence_date") == candidate.due_date.isoformat()
        ):
            bound = True
            break
    if not bound:
        raise HTTPException(status_code=409, detail="Occurrence audit binding integrity violation")
    return order


def preview_due(db: Session, actor: User, schedule_id: int, *,
                as_of: date, limit: int = 12) -> dict:
    """Read-only, authorized, bounded preview of due dates; never create orders."""
    row = _schedule(db, actor, schedule_id)
    if as_of > date.today():
        raise HTTPException(status_code=422, detail="Cannot preview future execution")
    if limit < 1 or limit > 120:
        raise HTTPException(status_code=422, detail="Invalid preview limit")
    if row.interval_days < 1 or row.interval_days > 3650:
        raise HTTPException(status_code=409, detail="Schedule interval integrity violation")
    due_dates: list[date] = []
    due = row.next_due_date
    if row.active:
        for _ in range(limit):
            if due > as_of or (row.end_date is not None and due > row.end_date):
                break
            due_dates.append(due)
            due += timedelta(days=row.interval_days)
    return {
        "schedule_id": row.id,
        "as_of": as_of,
        "next_due_date": row.next_due_date,
        "active": row.active,
        "due_dates": due_dates,
        "has_more": (
            row.active and due <= as_of
            and (row.end_date is None or due <= row.end_date)
        ),
    }


def generate_due(db: Session, actor: User, schedule_id: int, *, as_of: date):
    """Generate ONE due occurrence under row lock; retries return the same order."""
    row = _schedule(db, actor, schedule_id)
    if as_of > date.today():
        raise HTTPException(status_code=422, detail="Cannot create future occurrences")
    if not row.active:
        raise HTTPException(status_code=409, detail="Schedule is paused")
    # Lock the parent schedule to serialize two concurrent workers using PostgreSQL.
    row = db.query(Schedule).populate_existing().filter(Schedule.id == row.id).with_for_update().one()
    if not row.active:
        raise HTTPException(status_code=409, detail="Schedule is paused")
    _scope(db, actor, row.unit_id)  # Revalidate under the lock before any write.
    if row.end_date is not None and row.next_due_date > row.end_date:
        previous = _last_valid_occurrence(db, row, as_of)
        if previous is not None:
            return previous, False
        raise HTTPException(status_code=409, detail="Schedule end date reached")
    if row.next_due_date > as_of:
        previous = _last_valid_occurrence(db, row, as_of)
        if previous is not None:
            return previous, False
        raise HTTPException(status_code=409, detail="No occurrence is due")
    due = row.next_due_date
    existing = db.query(Occurrence).filter_by(schedule_id=row.id, due_date=due).first()
    if existing:
        previous = _last_valid_occurrence(db, row, as_of)
        if previous is None or previous.id != existing.work_order_id:
            raise HTTPException(status_code=409, detail="Occurrence link integrity violation")
        return previous, False
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
    row.updated_at = datetime.utcnow()
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
    schedule = read_schedule(db, actor, schedule_id)
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


def sweep_due(db: Session, *, as_of: date, catchup_limit: int = 12) -> dict[str, int]:
    """Daily worker pass, with bounded per-schedule catch-up and live actor reauthorization.

    This does not impersonate tenants or authorize dispatch, entry, or payments.
    All business writes and occurrence keys go through generate_due().
    """
    if as_of > date.today():
        raise ValueError("Cannot sweep a future date")
    if catchup_limit < 1 or catchup_limit > 120:
        raise ValueError("Invalid catch-up limit")
    counts = {"created": 0, "skipped": 0, "backlog": 0}
    cursor = 0
    while True:
        rows = db.query(Schedule.id, Schedule.organization_id, Schedule.created_by_id).filter(
            Schedule.id > cursor,
            Schedule.active.is_(True),
            Schedule.next_due_date <= as_of,
            or_(Schedule.end_date.is_(None), Schedule.next_due_date <= Schedule.end_date),
        ).order_by(Schedule.id).limit(100).all()
        if not rows:
            break
        for schedule_id, org_id, creator_id in rows:
            cursor = schedule_id
            actor = db.query(User).filter(
                User.id == creator_id, User.organization_id == org_id,
            ).first()
            if actor is None:
                counts["skipped"] += 1
                continue
            for _ in range(catchup_limit):
                try:
                    _, fresh = generate_due(db, actor, schedule_id, as_of=as_of)
                except HTTPException:
                    db.rollback()
                    counts["skipped"] += 1
                    break
                if not fresh:
                    break
                counts["created"] += 1
                updated = db.query(Schedule).filter(Schedule.id == schedule_id).one()
                if not updated.active or updated.next_due_date > as_of:
                    break
            if db.query(Schedule.id).filter(
                Schedule.id == schedule_id, Schedule.active.is_(True),
                Schedule.next_due_date <= as_of,
                or_(Schedule.end_date.is_(None), Schedule.next_due_date <= Schedule.end_date),
            ).first() is not None:
                counts["backlog"] += 1
    return counts
