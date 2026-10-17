"""Archive association-scoped staff payer hints when their source disappears."""
from sqlalchemy.orm import Session
from app.models.hoa_payer_draft import HOAPayerDraft
from app.services.audit import append_audit_log


def archive_payer_drafts(
    db: Session, *, organization_id: int, association_id: int, actor_id: int,
    action: str, property_id: int | None = None,
    proposal_id: int | None = None, contact_link_id: int | None = None,
) -> None:
    query = db.query(HOAPayerDraft).filter(
        HOAPayerDraft.organization_id == organization_id,
        HOAPayerDraft.association_id == association_id,
        HOAPayerDraft.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAPayerDraft.property_id == property_id)
    if proposal_id is not None:
        query = query.filter(HOAPayerDraft.proposal_id == proposal_id)
    if contact_link_id is not None:
        query = query.filter(HOAPayerDraft.contact_link_id == contact_link_id)
    for row in query.all():
        row.is_active = False
        row.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="hoa_payer_draft", entity_id=row.id, action=action,
            new_value={"association_id": association_id,
                       "property_id": row.property_id,
                       "proposal_id": row.proposal_id},
        )
