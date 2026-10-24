"""Staff-only correspondence draft API; no delivery, fine, debtor or GL effects."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_procedure_policy import HOAProcedurePolicy
from app.models.hoa_violation_correspondence import HOAViolationCorrespondenceDraft
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_violation_recipients import _prerequisites, _out as recipient_out
from app.services.audit import append_audit_log

router = APIRouter(
    prefix="/api/hoa/associations", tags=["HOA staff correspondence drafts"],
)


class CorrespondenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)

    @classmethod
    def _trim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Nonempty staff correspondence text required.")
        return value.strip()

    from pydantic import field_validator
    subject = field_validator("subject")(_trim)
    body = field_validator("body")(_trim)


class CorrespondenceOut(BaseModel):
    id: int
    case_id: int
    revision: int
    policy_revision: int
    recipient_contact_link_id: int
    recipient_user_id: int
    stage_snapshot: str
    draft_notice_on: date | None
    tentative_cure_on: date | None
    subject: str
    body: str
    prepared_at: datetime
    recipient_reference_current: bool
    policy_revision_current: bool
    case_stage_current: bool
    status: Literal["STAFF_DRAFT_NOT_SENT"] = "STAFF_DRAFT_NOT_SENT"
    legally_served: Literal[False] = False
    fine_assessed: Literal[False] = False


def _visible(db: Session, *, draft: HOAViolationCorrespondenceDraft,
             case, policy, recipient) -> CorrespondenceOut:
    # A past private draft is immutable, but today's reference validity is
    # shown separately. Never call a stale identity a current recipient.
    matched = False
    if (
        recipient is not None and recipient.is_active
        and draft.recipient_reference_id == recipient.id
        and draft.contact_link_id == recipient.contact_link_id
        and draft.matched_user_id == recipient.matched_user_id
    ):
        try:
            recipient_out(db, recipient)
            matched = True
        except HTTPException:
            matched = False
    return CorrespondenceOut(
        id=draft.id, case_id=draft.case_id, revision=draft.revision,
        policy_revision=draft.policy_revision,
        recipient_contact_link_id=draft.contact_link_id,
        recipient_user_id=draft.matched_user_id,
        stage_snapshot=draft.stage, draft_notice_on=draft.draft_notice_on,
        tentative_cure_on=draft.tentative_cure_on,
        subject=draft.subject, body=draft.body, prepared_at=draft.prepared_at,
        recipient_reference_current=matched,
        policy_revision_current=bool(
            policy and policy.is_active and policy.id == draft.policy_id
            and policy.revision == draft.policy_revision
        ),
        case_stage_current=case.stage == draft.stage,
    )


def _data(db: Session, *, org: int, assoc_id: int, property_id: int,
          case_id: int):
    recipient = db.query(HOAViolationRecipientDraft).filter(
        HOAViolationRecipientDraft.organization_id == org,
        HOAViolationRecipientDraft.association_id == assoc_id,
        HOAViolationRecipientDraft.property_id == property_id,
        HOAViolationRecipientDraft.case_id == case_id,
    ).first()
    policy = db.query(HOAProcedurePolicy).filter(
        HOAProcedurePolicy.organization_id == org,
        HOAProcedurePolicy.association_id == assoc_id,
        HOAProcedurePolicy.property_id == property_id,
        HOAProcedurePolicy.is_active.is_(True),
    ).first()
    return recipient, policy


@router.get("/{association_id}/staff-cases/{case_id}/correspondence",
            response_model=list[CorrespondenceOut])
def get_correspondence(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _prerequisites(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id, write=False,
    )
    recipient, policy = _data(
        db, org=org, assoc_id=assoc.id, property_id=property_id, case_id=case.id,
    )
    rows = db.query(HOAViolationCorrespondenceDraft).filter(
        HOAViolationCorrespondenceDraft.organization_id == org,
        HOAViolationCorrespondenceDraft.association_id == assoc.id,
        HOAViolationCorrespondenceDraft.property_id == property_id,
        HOAViolationCorrespondenceDraft.case_id == case.id,
    ).order_by(HOAViolationCorrespondenceDraft.revision).limit(51).all()
    if len(rows) > 50:
        raise HTTPException(status_code=422, detail="Correspondence history exceeds display limit.")
    response.headers["Cache-Control"] = "no-store"
    return [_visible(db, draft=row, case=case, policy=policy, recipient=recipient)
            for row in rows]


@router.post("/{association_id}/staff-cases/{case_id}/correspondence",
             response_model=CorrespondenceOut, status_code=201)
def prepare_correspondence(
    association_id: int, case_id: int, payload: CorrespondenceIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _prerequisites(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, case_id=case_id, write=True,
    )
    if case.stage not in {"NOTICE_DRAFT", "CURE_TRACKING", "HEARING_PLANNED", "FINE_PROPOSED"}:
        raise HTTPException(status_code=409, detail="Case is not in an active correspondence stage.")
    recipient, policy = _data(
        db, org=org, assoc_id=assoc.id, property_id=payload.property_id, case_id=case.id,
    )
    if recipient is None or not recipient.is_active:
        raise HTTPException(status_code=409, detail="A staff-linked verified-login recipient is required.")
    # Revalidate the current active contact and verified login on every write.
    recipient_out(db, recipient)
    if policy is None or not policy.draft_notice_text:
        raise HTTPException(status_code=409, detail="Current procedure text must be configured.")
    if not case.draft_notice_on:
        raise HTTPException(status_code=409, detail="Case notice draft preparation is missing.")

    last = db.query(HOAViolationCorrespondenceDraft).filter(
        HOAViolationCorrespondenceDraft.organization_id == org,
        HOAViolationCorrespondenceDraft.association_id == assoc.id,
        HOAViolationCorrespondenceDraft.property_id == payload.property_id,
        HOAViolationCorrespondenceDraft.case_id == case.id,
    ).order_by(HOAViolationCorrespondenceDraft.revision.desc()).with_for_update().first()
    if (
        last is not None and last.subject == payload.subject
        and last.body == payload.body
        and last.policy_id == policy.id and last.policy_revision == policy.revision
        and last.recipient_reference_id == recipient.id
        and last.contact_link_id == recipient.contact_link_id
        and last.matched_user_id == recipient.matched_user_id
        and last.stage == case.stage
        and last.draft_notice_on == case.draft_notice_on
        and last.tentative_cure_on == case.tentative_cure_on
    ):
        raise HTTPException(status_code=409, detail="Identical staff correspondence draft already exists.")
    revision = last.revision + 1 if last is not None else 1
    if revision > 50:
        raise HTTPException(status_code=422, detail="Correspondence draft history is full.")
    draft = HOAViolationCorrespondenceDraft(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, case_id=case.id, revision=revision,
        policy_id=policy.id, policy_revision=policy.revision,
        recipient_reference_id=recipient.id,
        contact_link_id=recipient.contact_link_id,
        matched_user_id=recipient.matched_user_id,
        stage=case.stage, draft_notice_on=case.draft_notice_on,
        tentative_cure_on=case.tentative_cure_on,
        subject=payload.subject, body=payload.body,
        prepared_by_id=current_user.id, prepared_at=datetime.utcnow(),
    )
    db.add(draft)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_correspondence_draft",
            entity_id=draft.id, action="staff_correspondence_prepared",
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "case_id": case.id, "revision": draft.revision,
                "recipient_reference_id": recipient.id,
                "policy_revision": policy.revision,
                "text_recorded_privately": True,
                "statutory_notice_sent": False, "fine_posted": False,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Correspondence revision changed concurrently.") from exc
    return _visible(db, draft=draft, case=case, policy=policy, recipient=recipient)
