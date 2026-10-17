"""Archive HOA staff ballot observations without reopening archived records."""
from sqlalchemy.orm import Session
from app.models.hoa_ballot import HOABallotRecord
from app.services.audit import append_audit_log


def archive_ballots(
    db: Session, *, organization_id: int, association_id: int,
    actor_id: int, action: str,
    property_id: int | None = None,
    meeting_draft_id: int | None = None,
    motion_draft_id: int | None = None,
    board_seat_id: int | None = None,
) -> None:
    query = db.query(HOABallotRecord).filter(
        HOABallotRecord.organization_id == organization_id,
        HOABallotRecord.association_id == association_id,
        HOABallotRecord.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOABallotRecord.property_id == property_id)
    if meeting_draft_id is not None:
        query = query.filter(HOABallotRecord.meeting_draft_id == meeting_draft_id)
    if motion_draft_id is not None:
        query = query.filter(HOABallotRecord.motion_draft_id == motion_draft_id)
    if board_seat_id is not None:
        query = query.filter(HOABallotRecord.board_seat_id == board_seat_id)
    for row in query.all():
        row.is_active = False
        row.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="hoa_ballot_record", entity_id=row.id,
            action=action, new_value={
                "association_id": association_id,
                "property_id": row.property_id,
                "meeting_draft_id": row.meeting_draft_id,
                "motion_draft_id": row.motion_draft_id,
            },
        )
