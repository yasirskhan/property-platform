"""Archive association-specific annual budgets when membership is removed.

Keep historical board and audit rows immutable. Explicit new draft is required
if an archived association/property is later re-linked.
"""
from sqlalchemy.orm import Session
from app.models.hoa_annual_budget import HOAAnnualBudget
from app.services.audit import append_audit_log


def archive_annual_budgets(
    db: Session, *, organization_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    query = db.query(HOAAnnualBudget).filter(
        HOAAnnualBudget.organization_id == organization_id,
        HOAAnnualBudget.association_id == association_id,
        HOAAnnualBudget.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAAnnualBudget.property_id == property_id)
    for record in query.all():
        record.is_active = False
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="hoa_annual_budget", entity_id=record.id,
            action=action,
            new_value={
                "association_id": association_id, "property_id": record.property_id,
                "calendar_year": record.calendar_year, "revision": record.revision,
            },
        )
