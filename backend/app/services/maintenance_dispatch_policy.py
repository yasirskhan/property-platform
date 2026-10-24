"""Resolved, scoped maintenance dispatch policy previews.

An advisory resolver only. This module does not send provider messages,
launch timers, accept offers or create financial transactions.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.maintenance_dispatch import (
    MaintenanceDispatchGroup, MaintenanceDispatchProperty, MaintenanceDispatchRule,
)
from app.models.property import Property
from app.schemas.work_order import MaintenanceEffectiveDispatchPolicy


def resolve_maintenance_dispatch_policy(
    db: Session, *, prop: Property, priority: object, now_utc: datetime | None = None,
) -> MaintenanceEffectiveDispatchPolicy:
    """Use an explicit exclusive binding or the organization's DEFAULT.

    Times use the organization's configured group timezone and standard
    Monday-Friday hours; holiday overrides have not been implemented.
    Missing configuration must not imply active dispatch or escalation.
    """
    raw = priority.value if hasattr(priority, "value") else priority
    urgency = "emergency" if str(raw).lower() == "emergency" else (
        "low" if str(raw).lower() == "low" else "normal"
    )
    if prop.organization_id is None or prop.is_active is False or prop.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Inactive or unscoped dispatch location")
    binding = db.query(MaintenanceDispatchProperty).filter(
        MaintenanceDispatchProperty.property_id == prop.id,
    ).first()
    if binding is not None and binding.organization_id != prop.organization_id:
        raise HTTPException(status_code=409, detail="Corrupt cross-organization dispatch binding")
    group_query = db.query(MaintenanceDispatchGroup).filter(
        MaintenanceDispatchGroup.organization_id == prop.organization_id,
    )
    if binding is None:
        group = group_query.filter(MaintenanceDispatchGroup.name_key == "default").first()
    else:
        group = group_query.filter(MaintenanceDispatchGroup.id == binding.group_id).first()
        if group is None or group.name_key == "default":
            raise HTTPException(status_code=409, detail="Invalid maintenance group binding")
    if group is None:
        return MaintenanceEffectiveDispatchPolicy(
            group_id=None, group_name=None, urgency=urgency, daypart=None,
            configured=False, status="NO_GROUP_CONFIGURED",
        )
    try:
        zone = ZoneInfo(group.timezone_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise HTTPException(status_code=409, detail="Invalid maintenance group timezone configuration")
    if not (0 <= group.business_start_hour < group.business_end_hour <= 24):
        raise HTTPException(status_code=409, detail="Invalid maintenance group business hours")
    moment = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(zone)
    business = (
        local.weekday() < 5 and
        group.business_start_hour <= local.hour < group.business_end_hour
    )
    daypart = "business_hours" if business else "after_hours"
    rule = db.query(MaintenanceDispatchRule).filter(
        MaintenanceDispatchRule.organization_id == prop.organization_id,
        MaintenanceDispatchRule.group_id == group.id,
        MaintenanceDispatchRule.urgency == urgency,
        MaintenanceDispatchRule.daypart == daypart,
    ).first()
    return MaintenanceEffectiveDispatchPolicy(
        group_id=group.id, group_name=group.name,
        urgency=urgency, daypart=daypart, configured=rule is not None,
        status="CONFIGURED_ADVISORY" if rule is not None else "RULE_NOT_CONFIGURED",
        first_target=rule.first_target if rule else None,
        backup_target=rule.backup_target if rule else None,
        timeout_minutes=rule.timeout_minutes if rule else None,
        escalate=rule.escalate if rule else False,
        primary_contact_user_id=rule.primary_contact_user_id if rule else None,
        backup_contact_user_id=rule.backup_contact_user_id if rule else None,
    )
