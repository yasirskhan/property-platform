"""Generic HOA ARC application lifecycle.

This workflow is operational staff tracking only. Prepared approval/denial
states have no legal effect until governing authority is separately verified.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_arc_application import (
    HOAARCApplication, HOAARCApplicationAttachment, HOAARCReviewEvent,
)
from app.models.hoa_arc_intake import HOAARCIntake
from app.models.hoa_association import HOAContactLink
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.routers.hoa_governing_evidence import _attachment, _require_attachment_feature
from app.schemas.hoa_arc_application import (
    HOAARCApplicationDetailOut, HOAARCApplicationIn, HOAARCApplicationOut,
    HOAARCAttachmentIn,
    HOAARCAttachmentOut, HOAARCReviewEventIn, HOAARCReviewEventOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA ARC application workflow"])

_TRANSITIONS = {
    "SUBMITTED": {"START_REVIEW": ("UNDER_REVIEW", None)},
    "UNDER_REVIEW": {
        "REQUEST_MORE_INFO": ("MORE_INFO_REQUESTED", None),
        "MARK_READY_FOR_DECISION": ("READY_FOR_DECISION", None),
    },
    "MORE_INFO_REQUESTED": {
        "RECORD_INFO_RECEIVED": ("INFO_RECEIVED", None),
    },
    "INFO_RECEIVED": {
        "START_REVIEW": ("UNDER_REVIEW", None),
        "MARK_READY_FOR_DECISION": ("READY_FOR_DECISION", None),
    },
    "READY_FOR_DECISION": {
        "PREPARE_APPROVAL": ("DECISION_PREPARED", "APPROVE"),
        "PREPARE_DENIAL": ("DECISION_PREPARED", "DENY"),
        "REQUEST_MORE_INFO": ("MORE_INFO_REQUESTED", None),
    },
    "DECISION_PREPARED": {
        "REQUEST_MORE_INFO": ("MORE_INFO_REQUESTED", None),
        "START_REVIEW": ("UNDER_REVIEW", None),
    },
}


def _intake(db: Session, *, org_id: int, association_id: int, property_id: int, intake_id: int) -> HOAARCIntake:
    row = db.query(HOAARCIntake).filter(
        HOAARCIntake.id == intake_id,
        HOAARCIntake.organization_id == org_id,
        HOAARCIntake.association_id == association_id,
        HOAARCIntake.property_id == property_id,
        HOAARCIntake.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="ARC intake not found.")
    return row


def _contact_link(db: Session, *, org_id: int, association_id: int, property_id: int, link_id: int):
    row = db.query(HOAContactLink, Contact).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).filter(
        HOAContactLink.id == link_id,
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org_id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Applicant contact reference not found.")
    return row


def _row(db: Session, *, org_id: int, association_id: int, property_id: int, application_id: int) -> HOAARCApplication:
    row = db.query(HOAARCApplication).filter(
        HOAARCApplication.id == application_id,
        HOAARCApplication.organization_id == org_id,
        HOAARCApplication.association_id == association_id,
        HOAARCApplication.property_id == property_id,
        HOAARCApplication.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="ARC application not found.")
    return row


def _events(db: Session, row: HOAARCApplication) -> list[HOAARCReviewEventOut]:
    return [
        HOAARCReviewEventOut(
            id=e.id, event_type=e.event_type, staff_note=e.staff_note,
            created_at=e.created_at,
        )
        for e in db.query(HOAARCReviewEvent).filter(
            HOAARCReviewEvent.organization_id == row.organization_id,
            HOAARCReviewEvent.application_id == row.id,
        ).order_by(HOAARCReviewEvent.id).limit(501).all()
    ]


def _attachments(db: Session, row: HOAARCApplication) -> list[HOAARCAttachmentOut]:
    records = db.query(HOAARCApplicationAttachment, EntityAttachment).join(
        EntityAttachment, EntityAttachment.id == HOAARCApplicationAttachment.attachment_id,
    ).filter(
        HOAARCApplicationAttachment.organization_id == row.organization_id,
        HOAARCApplicationAttachment.application_id == row.id,
        HOAARCApplicationAttachment.property_id == row.property_id,
        HOAARCApplicationAttachment.is_active.is_(True),
        EntityAttachment.organization_id == row.organization_id,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == row.property_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).order_by(HOAARCApplicationAttachment.id).limit(201).all()
    return [
        HOAARCAttachmentOut(
            id=link.id, attachment_id=attachment.id,
            filename=attachment.original_name, recorded_at=link.created_at,
        )
        for link, attachment in records
    ]


def _out(db: Session, row: HOAARCApplication) -> HOAARCApplicationOut:
    link, contact = _contact_link(
        db, org_id=row.organization_id, association_id=row.association_id,
        property_id=row.property_id, link_id=row.applicant_contact_link_id,
    )
    return HOAARCApplicationOut(
        id=row.id, association_id=row.association_id, property_id=row.property_id,
        intake_id=row.intake_id, applicant_contact_link_id=link.id,
        applicant_contact_name=contact.display_name, submitted_on=row.submitted_on,
        status=row.status, decision_preparation=row.decision_preparation,
        updated_at=row.updated_at,
    )


def _detail(db: Session, row: HOAARCApplication) -> HOAARCApplicationDetailOut:
    return HOAARCApplicationDetailOut(
        **_out(db, row).model_dump(),
        events=_events(db, row), attachments=_attachments(db, row),
    )


@router.get("/{association_id}/arc-applications", response_model=list[HOAARCApplicationOut])
def list_applications(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAARCApplication).filter(
        HOAARCApplication.organization_id == org_id,
        HOAARCApplication.association_id == assoc.id,
        HOAARCApplication.property_id == property_id,
        HOAARCApplication.is_active.is_(True),
    ).order_by(HOAARCApplication.id).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Too many ARC applications.")
    return [_out(db, row) for row in rows]


@router.get("/{association_id}/arc-applications/{application_id}", response_model=HOAARCApplicationDetailOut)
def get_application(
    association_id: int, application_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    row = _row(
        db, org_id=org_id, association_id=assoc.id,
        property_id=property_id, application_id=application_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return _detail(db, row)


@router.post("/{association_id}/arc-applications", response_model=HOAARCApplicationDetailOut, status_code=201)
def create_application(
    association_id: int, payload: HOAARCApplicationIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    intake = _intake(
        db, org_id=org_id, association_id=assoc.id,
        property_id=payload.property_id, intake_id=payload.intake_id,
    )
    _contact_link(
        db, org_id=org_id, association_id=assoc.id,
        property_id=payload.property_id, link_id=payload.applicant_contact_link_id,
    )
    existing = db.query(HOAARCApplication.id).filter(
        HOAARCApplication.organization_id == org_id,
        HOAARCApplication.intake_id == intake.id,
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="ARC intake already has an application.")
    row = HOAARCApplication(
        organization_id=org_id, association_id=assoc.id,
        property_id=payload.property_id, intake_id=intake.id,
        applicant_contact_link_id=payload.applicant_contact_link_id,
        submitted_on=payload.submitted_on, status="SUBMITTED",
        created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        event = HOAARCReviewEvent(
            organization_id=org_id, application_id=row.id,
            event_type="APPLICATION_SUBMITTED", staff_note=None,
            created_by_id=current_user.id,
        )
        db.add(event)
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_arc_application", entity_id=row.id,
            action="application_recorded",
            new_value={"association_id": assoc.id, "property_id": row.property_id, "status": row.status},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="ARC application changed concurrently.") from exc
    db.refresh(row)
    return _detail(db, row)


@router.post("/{association_id}/arc-applications/{application_id}/events",
             response_model=HOAARCApplicationDetailOut)
def add_review_event(
    association_id: int, application_id: int, payload: HOAARCReviewEventIn,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _row(
        db, org_id=org_id, association_id=assoc.id,
        property_id=property_id, application_id=application_id,
    )
    transition = _TRANSITIONS.get(row.status, {}).get(payload.event_type)
    if transition is None:
        raise HTTPException(status_code=409, detail="ARC review transition is not allowed from current status.")
    next_status, preparation = transition
    row.status = next_status
    row.decision_preparation = preparation
    row.updated_by_id = current_user.id
    event = HOAARCReviewEvent(
        organization_id=org_id, application_id=row.id,
        event_type=payload.event_type, staff_note=payload.staff_note,
        created_by_id=current_user.id,
    )
    db.add(event)
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_arc_application", entity_id=row.id,
        action="review_stage_recorded",
        new_value={"association_id": assoc.id, "property_id": row.property_id, "status": row.status},
    )
    db.commit()
    db.refresh(row)
    return _detail(db, row)


@router.post("/{association_id}/arc-applications/{application_id}/attachments",
             response_model=HOAARCAttachmentOut, status_code=201)
def add_application_attachment(
    association_id: int, application_id: int, payload: HOAARCAttachmentIn,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _require_attachment_feature(db, current_user)
    row = _row(
        db, org_id=org_id, association_id=assoc.id,
        property_id=property_id, application_id=application_id,
    )
    attachment = _attachment(
        db, org_id=org_id, prop_id=property_id, attachment_id=payload.attachment_id,
    )
    existing = db.query(HOAARCApplicationAttachment).filter(
        HOAARCApplicationAttachment.application_id == row.id,
        HOAARCApplicationAttachment.attachment_id == attachment.id,
        HOAARCApplicationAttachment.is_active.is_(True),
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Attachment already linked to ARC application.")
    link = HOAARCApplicationAttachment(
        organization_id=org_id, application_id=row.id,
        property_id=property_id, attachment_id=attachment.id,
        created_by_id=current_user.id,
    )
    db.add(link)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_arc_application_attachment", entity_id=link.id,
            action="private_attachment_linked",
            new_value={"application_id": row.id, "property_id": property_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attachment link changed concurrently.") from exc
    return HOAARCAttachmentOut(
        id=link.id, attachment_id=attachment.id,
        filename=attachment.original_name, recorded_at=link.created_at,
    )


@router.delete("/{association_id}/arc-applications/{application_id}/attachments/{link_id}", status_code=204)
def archive_application_attachment(
    association_id: int, application_id: int, link_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _require_attachment_feature(db, current_user)
    row = _row(
        db, org_id=org_id, association_id=assoc.id,
        property_id=property_id, application_id=application_id,
    )
    link = db.query(HOAARCApplicationAttachment).filter(
        HOAARCApplicationAttachment.id == link_id,
        HOAARCApplicationAttachment.organization_id == org_id,
        HOAARCApplicationAttachment.application_id == row.id,
        HOAARCApplicationAttachment.property_id == property_id,
        HOAARCApplicationAttachment.is_active.is_(True),
    ).first()
    if link is None:
        raise HTTPException(status_code=404, detail="ARC attachment link not found.")
    link.is_active = False
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_arc_application_attachment", entity_id=link.id,
        action="private_attachment_archived",
        new_value={"application_id": row.id, "property_id": property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/{association_id}/arc-applications/{application_id}", status_code=204)
def archive_application(
    association_id: int, application_id: int, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _row(
        db, org_id=org_id, association_id=assoc.id,
        property_id=property_id, application_id=application_id,
    )
    row.is_active = False
    row.updated_by_id = current_user.id
    for link in db.query(HOAARCApplicationAttachment).filter(
        HOAARCApplicationAttachment.organization_id == org_id,
        HOAARCApplicationAttachment.application_id == row.id,
        HOAARCApplicationAttachment.is_active.is_(True),
    ).all():
        link.is_active = False
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_arc_application", entity_id=row.id,
        action="application_archived",
        new_value={"association_id": assoc.id, "property_id": property_id, "status": row.status},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
