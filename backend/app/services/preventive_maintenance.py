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
    # A global MANAGER with only a CREW role on this property cannot
    # authorize schedules or source unattended maintenance work orders.
    if actor.role == UserRole.MANAGER:
        assigned_manager = db.query(PropertyAssignment.id).filter(
            PropertyAssignment.property_id == unit.property_id,
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.role == UserRole.MANAGER,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        ).first()
        if assigned_manager is None:
            raise HTTPException(status_code=403, detail="Active property manager assignment required")
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
            PropertyAssignment.role == UserRole.MANAGER,
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
        end_date=end_date, created_by_id=actor.id, executor_user_id=actor.id, active=True)
    db.add(row)
    db.flush()
    append_audit_log(db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
        organization_id=actor.organization_id, user_id=actor.id, action="created",
        new_value={"unit_id":unit.id, "property_id":unit.property_id, "interval_days":interval_days,
                   "next_due_date":next_due_date.isoformat(), "title":title,
                   "end_date":end_date.isoformat() if end_date is not None else None,
                   "executor_user_id": actor.id})
    db.commit()
    db.refresh(row)
    return row

def list_schedules(db: Session, actor: User, *, limit: int = 100, offset: int = 0, search: str = "", due_only: bool = False):
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
    term = search.strip()
    if len(term) > 100:
        raise HTTPException(status_code=422, detail="Invalid schedule search")
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Schedule.title.ilike(f"%{escaped}%", escape="\\"))
    if actor.role == UserRole.MANAGER:
        authorized_properties = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.role == UserRole.MANAGER,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(authorized_properties))
    if due_only:
        query = query.filter(
            Schedule.active.is_(True),
            Schedule.next_due_date <= date.today(),
            or_(Schedule.end_date.is_(None), Schedule.next_due_date <= Schedule.end_date),
        )
        return query.order_by(Schedule.next_due_date.asc(), Schedule.id.asc()).offset(offset).limit(limit).all()
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



def execution_status(db: Session, actor: User, schedule_id: int) -> dict:
    """Show the reason an authorized schedule is (or is not) executable.

    Read-only historical access is preserved, even for a retired property.
    """
    row = read_schedule(db, actor, schedule_id)
    executor_id = row.executor_user_id or row.created_by_id
    reason = None
    if not row.active:
        state = "paused"
        reason = "SCHEDULE_PAUSED"
    elif row.end_date is not None and row.next_due_date > row.end_date:
        state = "finished"
        reason = "SCHEDULE_FINISHED"
    else:
        executor = db.query(User).filter(
            User.id == executor_id, User.organization_id == row.organization_id,
        ).first()
        if executor is None:
            state = "blocked"
            reason = "OPERATOR_UNAVAILABLE"
        else:
            try:
                _scope(db, executor, row.unit_id)
            except HTTPException:
                state = "blocked"
                reason = ("OPERATOR_INACTIVE" if not executor.is_active or executor.deleted_at is not None
                          else "OPERATOR_OR_PROPERTY_INELIGIBLE")
            else:
                state = "ready"
    return {
        "schedule_id": row.id,
        "executor_user_id": executor_id,
        "status": state,
        "block_reason": reason,
        "due": state == "ready" and row.next_due_date <= date.today(),
    }


def batch_execution_health(db: Session, actor: User, schedule_ids: list[int]) -> list[dict]:
    """Bounded staff-only review of existing schedule execution health.

    Every record is independently authorized using the same historical scope as
    the single-schedule endpoint; mixed foreign/revoked IDs fail the entire batch.
    No work orders or transfers are written.
    """
    if not 1 <= len(schedule_ids) <= 100 or len(set(schedule_ids)) != len(schedule_ids):
        raise HTTPException(status_code=422, detail="Provide 1-100 distinct schedule IDs")
    return [execution_status(db, actor, schedule_id) for schedule_id in schedule_ids]


def assume_execution(db: Session, actor: User, schedule_id: int, *, reason: str) -> Schedule:
    """Staff can recover a stalled schedule without falsifying original authorship.

    A manager may only take over when the prior executor has lost authority.
    An administrator may make an audited proactive transfer. The schedule-row
    lock serializes this change against generation, pause and settings edits.
    """
    reason = reason.strip()
    if not 10 <= len(reason) <= 500:
        raise HTTPException(status_code=422, detail="Provide a 10-500 character transfer reason")
    scoped = _schedule(db, actor, schedule_id)
    row = db.query(Schedule).populate_existing().filter(
        Schedule.id == scoped.id, Schedule.organization_id == actor.organization_id,
    ).with_for_update().one()
    _scope(db, actor, row.unit_id)
    previous_id = row.executor_user_id or row.created_by_id
    if previous_id == actor.id:
        return row
    if actor.role != UserRole.ADMIN:
        previous = db.query(User).filter(
            User.id == previous_id, User.organization_id == row.organization_id,
        ).first()
        if previous is not None:
            try:
                _scope(db, previous, row.unit_id)
            except HTTPException:
                pass
            else:
                raise HTTPException(
                    status_code=409, detail="Current executor is authorized; ask an administrator to transfer",
                )
    row.executor_user_id = actor.id
    row.updated_at = datetime.utcnow()
    append_audit_log(
        db, entity_type="preventive_maintenance_schedule", entity_id=row.id,
        organization_id=actor.organization_id, user_id=actor.id,
        action="executor_transferred",
        old_value={"executor_user_id": previous_id},
        new_value={"executor_user_id": actor.id, "reason": reason},
    )
    db.commit()
    db.refresh(row)
    return row


def _assert_occurrence_audit_binding(db: Session, schedule: Schedule, candidate: Occurrence, order: WorkOrder) -> None:
    """Require durable creation evidence before exposing any linked work ID."""
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
    _assert_occurrence_audit_binding(db, schedule, candidate, order)
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


def generate_due(db: Session, actor: User, schedule_id: int, *, as_of: date,
                 expected_next_due_date: date | None = None,
                 recovery_reason: str | None = None,
                 recovery_root_work_order_id: int | None = None):
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
    if expected_next_due_date is not None and row.next_due_date != expected_next_due_date:
        raise HTTPException(status_code=409, detail="Schedule changed; review current recovery evidence again")
    if recovery_reason is not None:
        # Full original provenance is verified while the schedule row stays locked.
        reconcile_occurrences(db, actor, schedule_id)
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
    if recovery_reason is not None:
        # Each successful recovery occurrence has its OWN committed audit.
        # The root ID unambiguously binds later commits in the same manual
        # batch, including batches interrupted by a later failed transaction.
        first = recovery_root_work_order_id is None
        append_audit_log(db, entity_type="preventive_maintenance_schedule",
            entity_id=row.id, organization_id=actor.organization_id, user_id=actor.id,
            action="operator_recovery_initiated" if first else "operator_recovery_continued",
            old_value={"next_due_date": due.isoformat()},
            new_value={
                "reason": recovery_reason if first else None,
                "first_work_order_id": wo.id if first else recovery_root_work_order_id,
                "root_work_order_id": wo.id if first else recovery_root_work_order_id,
                "work_order_id": wo.id,
                "due_date": due.isoformat(),
                "as_of": as_of.isoformat(),
                "external_delivery_confirmed": False,
                "financial_posted": False,
            })
    db.commit()
    db.refresh(wo)
    return wo, True


def catch_up_due(db: Session, actor: User, schedule_id: int, *,
                 as_of: date, limit: int = 12,
                 expected_next_due_date: date | None = None,
                 recovery_reason: str | None = None) -> dict:
    """Explicit operator recovery of a bounded backlog, using the proven single-
    occurrence lock/audit/authorization transaction for EACH generated order.

    Partial progress is durable: a failed later occurrence may be retried
    safely; no attempted or failed occurrence is reported as created.
    """
    if limit < 1 or limit > 12:
        raise HTTPException(status_code=422, detail="Catch-up limit must be 1 to 12")
    if as_of > date.today():
        raise HTTPException(status_code=422, detail="Cannot generate future occurrences")
    if (expected_next_due_date is None) != (recovery_reason is None):
        raise HTTPException(status_code=422, detail="Recovery evidence and reason must be provided together")
    if recovery_reason is not None:
        recovery_reason = recovery_reason.strip()
        if not 10 <= len(recovery_reason) <= 500:
            raise HTTPException(status_code=422, detail="Provide a 10-500 character recovery reason")
    schedule = read_schedule(db, actor, schedule_id)
    if not schedule.active:
        raise HTTPException(status_code=409, detail="Schedule is paused")
    ids: list[int] = []
    for attempt in range(limit):
        order, created = generate_due(
            db, actor, schedule_id, as_of=as_of,
            expected_next_due_date=expected_next_due_date if attempt == 0 else None,
            recovery_reason=recovery_reason,
            recovery_root_work_order_id=ids[0] if ids else None,
        )
        if not created:
            break
        # generate_due always creates tenantless, nonfinancial staff orders.
        if order.tenant_id is not None or order.request_origin != "staff":
            raise HTTPException(status_code=409, detail="Invalid preventive occurrence")
        ids.append(order.id)
    current = read_schedule(db, actor, schedule_id)
    return {
        "schedule_id": current.id, "as_of": as_of,
        "created_work_order_ids": ids,
        "remaining_due": bool(
            current.active and current.next_due_date <= as_of
            and (current.end_date is None or current.next_due_date <= current.end_date)
        ),
    }




def recovery_receipts(db: Session, actor: User, schedule_id: int) -> list[dict]:
    """Verified, scoped operator receipts for each committed recovery work order.

    Original linked occurrence evidence is independently reconciled, not
    derived from paginated history or untrusted audit JSON. Historical manual
    generations that did not have operator-reviewed recovery are not included.
    """
    schedule = read_schedule(db, actor, schedule_id)
    reconcile_occurrences(db, actor, schedule_id)
    records = db.query(AuditLog).filter(
        AuditLog.organization_id == schedule.organization_id,
        AuditLog.entity_type == "preventive_maintenance_schedule",
        AuditLog.entity_id == schedule.id,
        AuditLog.action.in_(("operator_recovery_initiated", "operator_recovery_continued")),
    ).order_by(AuditLog.id.asc()).limit(501).all()
    if len(records) > 500:
        raise HTTPException(status_code=409, detail="Recovery evidence exceeds review bound")
    by_root: dict[int, dict] = {}
    seen_orders: set[int] = set()
    for record in records:
        try:
            data = json.loads(record.new_value or "null")
        except (TypeError, ValueError):
            data = None
        if not isinstance(data, dict):
            raise HTTPException(status_code=409, detail="Recovery original audit is unreadable")
        # Even historical/revoked operators must have belonged to this exact
        # organization. Never expose unrelated user identities from forged
        # private recovery history.
        if (record.user_id is None or db.query(User.id).filter(
                User.id == record.user_id,
                User.organization_id == schedule.organization_id,
        ).first() is None):
            raise HTTPException(status_code=409, detail="Recovery operator provenance is invalid")
        work_order_id = data.get("work_order_id", data.get("first_work_order_id"))
        root_id = data.get("root_work_order_id", data.get("first_work_order_id"))
        if (not isinstance(root_id, int) or root_id < 1
                or not isinstance(work_order_id, int) or work_order_id < 1
                or work_order_id in seen_orders
                or data.get("first_work_order_id") != root_id
                or data.get("financial_posted", False) is not False
                or data.get("external_delivery_confirmed", False) is not False):
            raise HTTPException(status_code=409, detail="Recovery original audit integrity violation")
        occurrence = db.query(Occurrence).filter(
            Occurrence.schedule_id == schedule.id,
            Occurrence.organization_id == schedule.organization_id,
            Occurrence.work_order_id == work_order_id,
        ).one_or_none()
        if (occurrence is None or data.get("due_date", occurrence.due_date.isoformat()) != occurrence.due_date.isoformat()):
            raise HTTPException(status_code=409, detail="Recovery occurrence provenance mismatch")
        if record.action == "operator_recovery_initiated":
            if root_id != work_order_id or root_id in by_root:
                raise HTTPException(status_code=409, detail="Recovery root audit integrity violation")
            reason = data.get("reason")
            if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 500:
                raise HTTPException(status_code=409, detail="Recovery explanation is missing")
            by_root[root_id] = {
                "root_work_order_id": root_id,
                "reason": reason,
                "operator_user_id": record.user_id,
                "created_work_orders": [],
            }
        elif root_id not in by_root or by_root[root_id]["operator_user_id"] != record.user_id:
            raise HTTPException(status_code=409, detail="Recovery continuation is unbound")
        seen_orders.add(work_order_id)
        by_root[root_id]["created_work_orders"].append({
            "work_order_id": work_order_id,
            "due_date": occurrence.due_date,
        })
    return list(reversed(list(by_root.values())))



def reconcile_occurrences(db: Session, actor: User, schedule_id: int) -> dict:
    """Read-only, bounded all-record integrity review for recovery operators.

    The regular paginated history deliberately omits unsafe cross-scope joins.
    Recovery must instead inspect *all* original occurrence rows and refuse to
    claim clean history when any row has lost its source-work-order link, its
    organization/property/tenantless scope, or its immutable creation proof.
    Never return an unvalidated foreign or forged work-order ID.
    """
    schedule = read_schedule(db, actor, schedule_id)
    candidates = db.query(Occurrence).filter(
        Occurrence.schedule_id == schedule.id,
    ).order_by(Occurrence.due_date.asc(), Occurrence.id.asc()).limit(501).all()
    if len(candidates) > 500:
        raise HTTPException(status_code=409, detail="Occurrence reconciliation exceeds 500 rows; operator review required")
    # Audit is append-only whereas a corrupt occurrence pointer or missing
    # occurrence row may disappear from ordinary filtered history. Check BOTH
    # directions, including orphan creation audits, before certifying recovery.
    # Fetch outside the organization filter to detect foreign-organization
    # audit records forged against this globally unique schedule ID.
    generation_audits = db.query(AuditLog).filter(
        AuditLog.entity_type == "preventive_maintenance_occurrence",
        AuditLog.entity_id == schedule.id,
        AuditLog.action == "generated",
    ).order_by(AuditLog.id.asc()).limit(501).all()
    if len(generation_audits) > 500 or len(generation_audits) != len(candidates):
        raise HTTPException(status_code=409, detail="Original occurrence/audit count mismatch")
    original_proofs = set()
    for audit in generation_audits:
        if audit.organization_id != schedule.organization_id:
            raise HTTPException(status_code=409, detail="Original occurrence audit scope is invalid")
        try:
            data = json.loads(audit.new_value or "null")
        except (ValueError, TypeError):
            data = None
        if (not isinstance(data, dict)
                or type(data.get("schedule_id")) is not int
                or data["schedule_id"] != schedule.id
                or type(data.get("work_order_id")) is not int
                or data["work_order_id"] < 1
                or not isinstance(data.get("due_date"), str)):
            raise HTTPException(status_code=409, detail="Original generation proof is malformed")
        original_proofs.add((data["due_date"], data["work_order_id"]))
    if len(original_proofs) != len(generation_audits):
        raise HTTPException(status_code=409, detail="Duplicate original generation proofs")

    previous_due = None
    latest_id = None
    for occurrence in candidates:
        if (occurrence.organization_id != schedule.organization_id
                or occurrence.due_date > date.today()
                or (previous_due is not None and occurrence.due_date <= previous_due)):
            raise HTTPException(status_code=409, detail="Schedule occurrence provenance integrity violation")
        work_order = db.query(WorkOrder).filter(
            WorkOrder.id == occurrence.work_order_id,
            WorkOrder.property_id == schedule.property_id,
            WorkOrder.unit_id == schedule.unit_id,
        ).first()
        if (work_order is None or work_order.tenant_id is not None
                or work_order.request_origin != "staff"
                or work_order.permission_to_enter is not False):
            raise HTTPException(status_code=409, detail="Schedule original work-order link is invalid")
        _assert_occurrence_audit_binding(db, schedule, occurrence, work_order)
        if (occurrence.due_date.isoformat(), work_order.id) not in original_proofs:
            raise HTTPException(status_code=409, detail="Original occurrence creation proof mismatch")
        previous_due = occurrence.due_date
        latest_id = work_order.id
    if previous_due is not None and schedule.next_due_date <= previous_due:
        raise HTTPException(status_code=409, detail="Schedule next due cursor conflicts with historical occurrences")
    return {
        "schedule_id": schedule.id,
        "verified_occurrences": len(candidates),
        "latest_due_date": previous_due,
        "latest_work_order_id": latest_id,
        "next_due_date": schedule.next_due_date,
        "integrity_status": "VERIFIED",
        "read_only": True,
        "work_orders_created": 0,
        "automatic_dispatch": False,
        "financial_posted": False,
    }


def list_occurrences(db: Session, actor: User, schedule_id: int,
                     *, limit: int = 100, offset: int = 0):
    """Authorized durable evidence for every generated occurrence."""
    schedule = read_schedule(db, actor, schedule_id)
    # Join through the real work-order unit/property, not untrusted historical
    # label columns: a corrupted occurrence must never expose foreign work IDs.
    candidates = db.query(Occurrence).join(
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
    # A same-unit manually created order is not a valid replacement for a
    # scheduled occurrence: its immutable creation evidence must match.
    for occurrence in candidates:
        work_order = db.query(WorkOrder).filter(WorkOrder.id == occurrence.work_order_id).one()
        _assert_occurrence_audit_binding(db, schedule, occurrence, work_order)
    return candidates


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
        rows = db.query(Schedule.id, Schedule.organization_id, Schedule.created_by_id, Schedule.executor_user_id).filter(
            Schedule.id > cursor,
            Schedule.active.is_(True),
            Schedule.next_due_date <= as_of,
            or_(Schedule.end_date.is_(None), Schedule.next_due_date <= Schedule.end_date),
        ).order_by(Schedule.id).limit(100).all()
        if not rows:
            break
        for schedule_id, org_id, creator_id, executor_id in rows:
            cursor = schedule_id
            actor = db.query(User).filter(
                User.id == (executor_id or creator_id), User.organization_id == org_id,
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
