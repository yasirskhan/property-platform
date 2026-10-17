"""Soft-cancel reserve planning on association/property unlink without GL effects."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.hoa_reserve_movement_draft import HOAReserveMovementDraft
from app.services.audit import append_audit_log


def cancel_reserve_plans(
    db: Session, *, organization_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    q = db.query(HOAReserveMovementDraft).filter(
        HOAReserveMovementDraft.organization_id == organization_id,
        HOAReserveMovementDraft.association_id == association_id,
        HOAReserveMovementDraft.status == "DRAFT",
    )
    if property_id is not None:
        q = q.filter(HOAReserveMovementDraft.property_id == property_id)
    for row in q.all():
        row.status = "CANCELLED"
        row.cancelled_at = datetime.utcnow()
        row.cancelled_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="hoa_reserve_movement_draft", entity_id=row.id,
            action=action, new_value={"association_id": association_id,
                                     "property_id": row.property_id},
        )
