"""Cascade staff board proposals on association/property/contact unlink."""
from sqlalchemy.orm import Session
from app.models.hoa_board import HOABoardSeat, HOABoardRuleDraft
from app.services.audit import append_audit_log


def archive_board_proposals(
    db: Session, *, organization_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
    contact_link_id: int | None = None,
) -> None:
    if contact_link_id is None:
        models = (HOABoardSeat, HOABoardRuleDraft)
    else:
        models = (HOABoardSeat,)
    for model in models:
        query = db.query(model).filter(
            model.organization_id == organization_id,
            model.association_id == association_id,
            model.is_active.is_(True),
        )
        if property_id is not None:
            query = query.filter(model.property_id == property_id)
        if contact_link_id is not None:
            query = query.filter(model.contact_link_id == contact_link_id)
        for row in query.all():
            row.is_active = False
            row.updated_by_id = actor_id
            db.flush()
            append_audit_log(
                db, organization_id=organization_id, user_id=actor_id,
                entity_type=("hoa_board_seat" if isinstance(row, HOABoardSeat)
                             else "hoa_board_rule_draft"),
                entity_id=row.id, action=action,
                new_value={
                    "association_id": row.association_id,
                    "property_id": row.property_id,
                },
            )
