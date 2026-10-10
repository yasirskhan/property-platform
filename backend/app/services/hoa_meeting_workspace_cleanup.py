"""Archive dependent staff meeting references without resurrecting on HOA relink."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.hoa_meeting_workspace import HOAMeetingParticipation, HOAMotionDraft
from app.models.hoa_meeting_minutes import HOAMeetingMinutesDraft
from app.services.audit import append_audit_log
from app.services.hoa_ballot_cleanup import archive_ballots


def archive_meeting_workspace(
    db: Session, *, organization_id: int, association_id: int,
    property_id: int, meeting_draft_id: int, actor_id: int,
    action: str,
) -> None:
    archive_ballots(
        db, organization_id=organization_id, association_id=association_id,
        property_id=property_id, meeting_draft_id=meeting_draft_id,
        actor_id=actor_id, action=action,
    )
    for model, entity in (
        (HOAMeetingMinutesDraft, "hoa_meeting_minutes_draft"),
        (HOAMeetingParticipation, "hoa_meeting_participation"),
        (HOAMotionDraft, "hoa_motion_draft"),
    ):
        records = db.query(model).filter(
            model.organization_id == organization_id,
            model.association_id == association_id,
            model.property_id == property_id,
            model.meeting_draft_id == meeting_draft_id,
            model.is_active.is_(True),
        ).all()
        for record in records:
            record.is_active = False
            record.updated_by_id = actor_id
            db.flush()
            append_audit_log(
                db, organization_id=organization_id, user_id=actor_id,
                entity_type=entity, entity_id=record.id, action=action,
                new_value={
                    "association_id": association_id,
                    "property_id": property_id,
                    "meeting_draft_id": meeting_draft_id,
                },
            )


def archive_contact_participation(
    db: Session, *, organization_id: int, association_id: int,
    property_id: int, contact_link_id: int, actor_id: int,
    action: str,
) -> None:
    """Contact relink may restore the link, but never the former attendance claim."""
    records = db.query(HOAMeetingParticipation).filter(
        HOAMeetingParticipation.organization_id == organization_id,
        HOAMeetingParticipation.association_id == association_id,
        HOAMeetingParticipation.property_id == property_id,
        HOAMeetingParticipation.contact_link_id == contact_link_id,
        HOAMeetingParticipation.is_active.is_(True),
    ).all()
    for record in records:
        record.is_active = False
        record.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="hoa_meeting_participation", entity_id=record.id,
            action=action,
            new_value={
                "association_id": association_id,
                "property_id": property_id,
                "meeting_draft_id": record.meeting_draft_id,
            },
        )
