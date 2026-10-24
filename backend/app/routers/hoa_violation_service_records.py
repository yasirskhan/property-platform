"""Explicit board-recorded evidence of an actual notice-service event.

This captures association-reported service of an exact correspondence revision,
not a legal validity determination or an SMTP receipt. No money is posted.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_violation_evidence import HOAViolationEvidence
from app.models.hoa_violation_correspondence import HOAViolationCorrespondenceDraft
from app.models.hoa_violation_service_record import HOAViolationServiceRecord
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_violation_recipients import _prerequisites, _out as recipient_out
from app.routers.hoa_violation_correspondence import _data
from app.schemas.hoa_violation_service_record import HOAServiceRecordIn, HOAServiceRecordOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA service evidence"])


def _out(row: HOAViolationServiceRecord) -> HOAServiceRecordOut:
    return HOAServiceRecordOut(
        id=row.id, case_id=row.case_id,
        correspondence_id=row.correspondence_id,
        correspondence_revision=row.correspondence_revision,
        policy_revision=row.policy_revision,
        member_user_id=row.member_user_id,
        proof_attachment_id=row.service_proof_attachment_id,
        delivery_method=row.delivery_method, served_on=row.served_on,
        cure_earliest_on=row.cure_earliest_on,
        hearing_request_earliest_on=row.hearing_request_earliest_on,
        board_seat_id=row.board_seat_id, recorded_at=row.recorded_at,
    )


def _scope(db, actor, association_id, property_id, case_id, write):
    org, association, case = _prerequisites(
        db, actor=actor, association_id=association_id,
        property_id=property_id, case_id=case_id, write=write,
    )
    return org, association, case


@router.get("/{association_id}/staff-cases/{case_id}/service-record",
            response_model=HOAServiceRecordOut | None)
def get_service_record(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, association, case = _scope(
        db, current_user, association_id, property_id, case_id, False,
    )
    row = db.query(HOAViolationServiceRecord).filter(
        HOAViolationServiceRecord.organization_id == org,
        HOAViolationServiceRecord.association_id == association.id,
        HOAViolationServiceRecord.property_id == property_id,
        HOAViolationServiceRecord.case_id == case.id,
    ).first()
    response.headers["Cache-Control"] = "no-store"
    return _out(row) if row is not None else None


@router.post("/{association_id}/staff-cases/{case_id}/service-record",
             response_model=HOAServiceRecordOut, status_code=201)
def record_service(
    association_id: int, case_id: int, payload: HOAServiceRecordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, association, case = _scope(
        db, current_user, association_id, payload.property_id, case_id, True,
    )
    board_org, board_association, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    if board_org != org or board_association.id != association.id:
        raise HTTPException(status_code=403, detail="Association board scope differs.")
    old = db.query(HOAViolationServiceRecord).filter(
        HOAViolationServiceRecord.organization_id == org,
        HOAViolationServiceRecord.request_key == payload.request_key,
    ).first()
    if old is not None:
        same = (
            old.association_id == association.id
            and old.property_id == payload.property_id
            and old.case_id == case.id
            and old.correspondence_id == payload.correspondence_id
            and old.correspondence_revision == payload.correspondence_revision
            and old.policy_revision == payload.policy_revision
            and old.member_user_id == payload.member_user_id
            and old.service_proof_attachment_id == payload.proof_attachment_id
            and old.delivery_method == payload.delivery_method
            and old.served_on == payload.served_on
        )
        if not same:
            raise HTTPException(status_code=409, detail="Service request key already used.")
        return _out(old)
    if case.stage not in {"NOTICE_DRAFT", "CURE_TRACKING", "HEARING_PLANNED", "FINE_PROPOSED"}:
        raise HTTPException(status_code=409, detail="This case stage does not accept a service record.")
    if case.draft_notice_on is None or not case.draft_notice_on <= payload.served_on <= date.today():
        raise HTTPException(status_code=422, detail="Service date must follow recorded draft preparation and cannot be future-dated.")
    recipient, policy = _data(
        db, org=org, assoc_id=association.id,
        property_id=payload.property_id, case_id=case.id,
    )
    if recipient is None or not recipient.is_active:
        raise HTTPException(status_code=409, detail="Live matching recipient required.")
    current = recipient_out(db, recipient)
    if (current.matched_user_id != payload.member_user_id
        or recipient.matched_user_id != payload.member_user_id):
        raise HTTPException(status_code=409, detail="Service recipient does not match verified member.")
    if (policy is None or not policy.draft_notice_text
        or policy.cure_preparation_days is None
        or policy.hearing_request_days is None
        or policy.revision != payload.policy_revision):
        raise HTTPException(status_code=409, detail="Current notice, cure and hearing procedure required.")
    notice = db.query(HOAViolationCorrespondenceDraft).filter(
        HOAViolationCorrespondenceDraft.id == payload.correspondence_id,
        HOAViolationCorrespondenceDraft.organization_id == org,
        HOAViolationCorrespondenceDraft.association_id == association.id,
        HOAViolationCorrespondenceDraft.property_id == payload.property_id,
        HOAViolationCorrespondenceDraft.case_id == case.id,
        HOAViolationCorrespondenceDraft.revision == payload.correspondence_revision,
        HOAViolationCorrespondenceDraft.policy_revision == policy.revision,
        HOAViolationCorrespondenceDraft.recipient_reference_id == recipient.id,
        HOAViolationCorrespondenceDraft.matched_user_id == payload.member_user_id,
        HOAViolationCorrespondenceDraft.contact_link_id == recipient.contact_link_id,
    ).first()
    latest = db.query(HOAViolationCorrespondenceDraft.id).filter(
        HOAViolationCorrespondenceDraft.organization_id == org,
        HOAViolationCorrespondenceDraft.association_id == association.id,
        HOAViolationCorrespondenceDraft.property_id == payload.property_id,
        HOAViolationCorrespondenceDraft.case_id == case.id,
    ).order_by(HOAViolationCorrespondenceDraft.revision.desc()).first()
    if (notice is None or latest is None or latest.id != notice.id
        or notice.stage != "NOTICE_DRAFT"):
        raise HTTPException(status_code=409, detail="Exact latest notice-draft correspondence required.")
    proof = db.query(EntityAttachment).filter(
        EntityAttachment.id == payload.proof_attachment_id,
        EntityAttachment.organization_id == org,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == payload.property_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.deleted_at.is_(None),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).first()
    if proof is None:
        raise HTTPException(status_code=404, detail="Private same-property proof attachment required.")
    if db.query(HOAViolationEvidence.id).filter(
        HOAViolationEvidence.attachment_id == proof.id,
        HOAViolationEvidence.organization_id == org,
        HOAViolationEvidence.association_id == association.id,
        HOAViolationEvidence.property_id == payload.property_id,
        HOAViolationEvidence.case_id == case.id,
        HOAViolationEvidence.is_active.is_(True),
    ).first() is None:
        raise HTTPException(status_code=404, detail="Proof must be active private evidence linked to this case.")
    if db.query(HOAViolationServiceRecord.id).filter(
        HOAViolationServiceRecord.organization_id == org,
        HOAViolationServiceRecord.case_id == case.id,
    ).first():
        raise HTTPException(status_code=409, detail="Case service has already been recorded.")
    try:
        cure_on = payload.served_on + timedelta(days=policy.cure_preparation_days)
        hearing_on = payload.served_on + timedelta(days=policy.hearing_request_days)
    except OverflowError as exc:
        raise HTTPException(status_code=422, detail="Service deadlines outside supported date range.") from exc
    row = HOAViolationServiceRecord(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, case_id=case.id,
        correspondence_id=notice.id,
        correspondence_revision=notice.revision,
        policy_revision=policy.revision,
        contact_link_id=recipient.contact_link_id,
        member_user_id=payload.member_user_id,
        board_seat_id=seat.id,
        service_proof_attachment_id=proof.id,
        delivery_method=payload.delivery_method,
        served_on=payload.served_on,
        cure_earliest_on=cure_on, hearing_request_earliest_on=hearing_on,
        request_key=payload.request_key,
        recorded_by_id=current_user.id, recorded_at=datetime.utcnow(),
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_service_record", entity_id=row.id,
            action="association_service_evidence_recorded",
            new_value={
                "association_id": association.id, "property_id": payload.property_id,
                "case_id": case.id, "correspondence_id": notice.id,
                "policy_revision": policy.revision, "board_seat_id": seat.id,
                "proof_attachment_id": proof.id,
                "member_user_id": payload.member_user_id,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent service record or duplicate key.") from exc
    db.refresh(row)
    return _out(row)
