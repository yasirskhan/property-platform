"""Soft-archive HOA ARC application state when a prerequisite scope is removed."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.hoa_arc_application import HOAARCApplication, HOAARCApplicationAttachment
from app.services.audit import append_audit_log


def archive_arc_applications(
    db: Session, *,
    organization_id: int,
    association_id: int,
    actor_id: int,
    action: str,
    property_id: int | None = None,
    intake_id: int | None = None,
    contact_link_id: int | None = None,
) -> int:
    query = db.query(HOAARCApplication).filter(
        HOAARCApplication.organization_id == organization_id,
        HOAARCApplication.association_id == association_id,
        HOAARCApplication.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAARCApplication.property_id == property_id)
    if intake_id is not None:
        query = query.filter(HOAARCApplication.intake_id == intake_id)
    if contact_link_id is not None:
        query = query.filter(HOAARCApplication.applicant_contact_link_id == contact_link_id)
    affected = query.all()
    if any(row.status in {"APPROVED", "DENIED"} for row in affected):
        raise HTTPException(
            status_code=409,
            detail="Recorded board decisions prevent archiving this association reference.",
        )
    count = 0
    for row in affected:
        row.is_active = False
        row.updated_by_id = actor_id
        for link in db.query(HOAARCApplicationAttachment).filter(
            HOAARCApplicationAttachment.organization_id == organization_id,
            HOAARCApplicationAttachment.application_id == row.id,
            HOAARCApplicationAttachment.is_active.is_(True),
        ).all():
            link.is_active = False
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="hoa_arc_application", entity_id=row.id,
            action=action,
            new_value={
                "association_id": association_id,
                "property_id": row.property_id,
                "status": row.status,
            },
        )
        count += 1
    return count
