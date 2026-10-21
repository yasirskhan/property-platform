"""System-generated in-app escalation evidence for overdue policy-bound crew offers.

No external notification, automatic reassignment, payroll, invoice or vendor
approval. The worker is disabled by default and requires BOTH operator release
and persisted Owner/Admin group intent. Every event is tied to one immutable
crew-assignment timestamp and never impersonates an employee.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.maintenance_dispatch import MaintenanceDispatchGroup
from app.models.maintenance_dispatch_auto_notice import MaintenanceDispatchAutoNotice
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.services.audit import append_audit_log
from app.services.maintenance_dispatch_policy import resolve_maintenance_dispatch_policy


def sweep_due_auto_notices(
    db: Session, *, now_utc: datetime | None = None, execution_enabled: bool | None = None,
) -> dict[str, int | bool]:
    """Materialize at most 200 genuinely overdue, opt-in policy offers per run.

    PostgreSQL locks properties before work orders, matching existing offer
    transactions. Unique (work_order_id, assigned_at) prevents duplicate
    evidence even when job delivery or process execution is retried.
    """
    enabled = (settings.DISPATCH_AUTO_REVIEW_ENABLED if execution_enabled is None
               else execution_enabled)
    if not enabled:
        return {"enabled": False, "created": 0, "checked": 0}
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Automation sweep requires aware UTC time")
    now_naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    # Correlated candidates prevent the fixed first-200 scan from repeatedly
    # selecting already-noticed or unrelated manual assignments. Detailed
    # crew, group, timing and audit payload checks still run under row locks.
    already_recorded = db.query(MaintenanceDispatchAutoNotice.id).filter(
        MaintenanceDispatchAutoNotice.work_order_id == WorkOrder.id,
        MaintenanceDispatchAutoNotice.assigned_at == WorkOrder.assigned_at,
    ).exists()
    policy_origin_exists = db.query(AuditLog.id).filter(
        AuditLog.entity_type == "work_order",
        AuditLog.entity_id == WorkOrder.id,
        AuditLog.action == "dispatch_policy_offer_authorized",
    ).exists()
    ids = [row[0] for row in db.query(WorkOrder.id).filter(
        ~already_recorded,
        policy_origin_exists,
        WorkOrder.status == WorkOrderStatus.ASSIGNED,
        WorkOrder.assignment_response == "pending",
        WorkOrder.assigned_at.isnot(None),
        WorkOrder.assigned_at <= now_naive - timedelta(minutes=1),
    ).order_by(WorkOrder.assigned_at.asc(), WorkOrder.id.asc()).limit(200).all()]
    created = 0
    for work_order_id in ids:
        failed = False
        try:
            # Read immutable location identity, then lock the actual property
            # before the work order to match the dispatch/schedule lock order.
            location = db.query(WorkOrder.property_id).filter(
                WorkOrder.id == work_order_id,
            ).first()
            if not location:
                continue
            prop = db.query(Property).filter(Property.id == location[0]).with_for_update().first()
            order = db.query(WorkOrder).filter(
                WorkOrder.id == work_order_id,
            ).with_for_update().populate_existing().first()
            if not order or not prop:
                continue
            if (order.status != WorkOrderStatus.ASSIGNED
                    or order.assignment_response != "pending"
                    or order.assigned_to_id is None or order.assigned_at is None):
                continue
            unit = db.query(Unit).filter(
                Unit.id == order.unit_id, Unit.property_id == prop.id,
                Unit.is_active.is_(True), Unit.deleted_at.is_(None),
            ).first()
            org = db.query(Organization).filter(
                Organization.id == prop.organization_id,
                Organization.is_active.is_(True), Organization.deleted_at.is_(None),
            ).first()
            if (not org or not unit or not prop.is_active or prop.deleted_at is not None):
                continue
            crew = db.query(User).join(
                PropertyAssignment,
                PropertyAssignment.user_id == User.id,
            ).filter(
                User.id == order.assigned_to_id,
                User.organization_id == org.id,
                User.role == UserRole.CREW,
                User.is_active.is_(True), User.deleted_at.is_(None),
                PropertyAssignment.property_id == prop.id,
                PropertyAssignment.role == UserRole.CREW,
                PropertyAssignment.is_active.is_(True),
                PropertyAssignment.deleted_at.is_(None),
            ).first()
            if crew is None:
                continue
            policy = resolve_maintenance_dispatch_policy(
                db, prop=prop, priority=order.priority,
                now_utc=order.assigned_at.replace(tzinfo=timezone.utc),
            )
            if (not policy.configured or not policy.escalate
                    or policy.first_target != "crew" or policy.group_id is None
                    or policy.timeout_minutes is None):
                continue
            group = db.query(MaintenanceDispatchGroup).filter(
                MaintenanceDispatchGroup.id == policy.group_id,
                MaintenanceDispatchGroup.organization_id == org.id,
                MaintenanceDispatchGroup.automation_requested.is_(True),
            ).first()
            if group is None:
                continue
            if now_naive < order.assigned_at + timedelta(minutes=policy.timeout_minutes):
                continue
            existing = db.query(MaintenanceDispatchAutoNotice.id).filter(
                MaintenanceDispatchAutoNotice.work_order_id == order.id,
                MaintenanceDispatchAutoNotice.assigned_at == order.assigned_at,
            ).first()
            if existing:
                continue
            # Only policy-confirmed offers may enter automated escalation.
            # A manually assigned or older, unrelated assignment is excluded.
            audits = db.query(AuditLog).filter(
                AuditLog.organization_id == org.id,
                AuditLog.entity_type == "work_order",
                AuditLog.entity_id == order.id,
                AuditLog.action == "dispatch_policy_offer_authorized",
                AuditLog.created_at >= order.assigned_at - timedelta(minutes=2),
                AuditLog.created_at <= order.assigned_at + timedelta(minutes=2),
            ).order_by(AuditLog.id.desc()).limit(3).all()
            origin_verified = False
            for audit in audits:
                try:
                    evidence = json.loads(audit.new_value or "null")
                except (ValueError, TypeError):
                    continue
                if (isinstance(evidence, dict)
                        and evidence.get("crew_user_id") == crew.id
                        and evidence.get("group_id") == group.id
                        and evidence.get("source") == "staff_confirmed_policy_offer"):
                    origin_verified = True
                    break
            if not origin_verified:
                continue
            row = MaintenanceDispatchAutoNotice(
                organization_id=org.id, work_order_id=order.id,
                property_id=prop.id, crew_user_id=crew.id,
                group_id=group.id, assigned_at=order.assigned_at,
                timeout_minutes=policy.timeout_minutes,
            )
            db.add(row)
            db.flush()
            append_audit_log(
                db, entity_type="maintenance_dispatch_auto_notice",
                entity_id=row.id, organization_id=org.id,
                user_id=None, action="system_attention_recorded",
                new_value={
                    "work_order_id": order.id,
                    "assigned_at": order.assigned_at.isoformat(),
                    "crew_user_id": crew.id,
                    "group_id": group.id,
                    "source": "system_sweep",
                    "in_app_attention_only": True,
                    "external_delivery_confirmed": False,
                    "assignment_changed": False,
                    "financial_effect": False,
                },
            )
            created += 1
        except Exception:
            failed = True
            db.rollback()
            raise
        finally:
            # Excluded rows release locks, while failures always roll back.
            if not failed:
                db.commit()
    return {"enabled": True, "created": created, "checked": len(ids)}
