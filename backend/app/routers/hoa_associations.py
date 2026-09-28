"""Organization-scoped HOA roster only; never an assessment or official HOA certification."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_association import HOAAssociation, HOAPropertyMembership, HOAContactLink
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.hoa_observation import HOAObservation
from app.models.hoa_meeting_draft import HOAMeetingDraft
from app.models.hoa_arc_intake import HOAARCIntake
from app.models.hoa_governing_evidence import HOAGoverningEvidence
from app.models.hoa_procedure_policy import HOAProcedurePolicy
from app.models.hoa_violation_case import HOAViolationCase
from app.models.hoa_reserve_account import HOAReserveAccount
from app.models.contact import Contact
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.hoa_association import HOAAssociationIn, HOAAssociationOut, HOAContactLinkIn, HOAContactLinkOut
from app.services.audit import append_audit_log
from app.services.hoa_meeting_workspace_cleanup import archive_meeting_workspace, archive_contact_participation
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA association inventory"])
# Existing compliance capability, no new unrelated per-field flag.
FEATURE_KEY = "release.properties.compliance"


def _access(db: Session, actor: User, *, write: bool = False) -> int:
    if (
        actor.organization_id is None or not actor.is_active or actor.deleted_at is not None
        or actor.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or (write and actor.role not in {UserRole.ADMIN, UserRole.OWNER})
        or not permission_allows_user(db, user=actor, menu_key="PROPERTIES.ALL")
    ):
        raise HTTPException(status_code=403, detail="HOA property permission required.")
    decision = next(
        (x for x in resolve_customer_features(db, user=actor) if x.key == FEATURE_KEY), None
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="HOA inventory unavailable.")
    return int(actor.organization_id)


def _visible(db: Session, *, org_id: int, actor: User):
    query = db.query(Property).filter(
        Property.organization_id == org_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if actor.role == UserRole.MANAGER:
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    return query


def _association(db: Session, *, org_id: int, association_id: int) -> HOAAssociation:
    row = db.query(HOAAssociation).filter(
        HOAAssociation.id == association_id,
        HOAAssociation.organization_id == org_id,
        HOAAssociation.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Association not found.")
    return row


def _members(db: Session, *, org_id: int, actor: User, association_id: int) -> list[Property]:
    return _visible(db, org_id=org_id, actor=actor).join(
        HOAPropertyMembership, HOAPropertyMembership.property_id == Property.id,
    ).filter(
        HOAPropertyMembership.organization_id == org_id,
        HOAPropertyMembership.association_id == association_id,
    ).order_by(Property.name.asc(), Property.id.asc()).all()


def _out(row: HOAAssociation, members: list[Property]) -> HOAAssociationOut:
    return HOAAssociationOut(
        id=row.id, name=row.name, property_ids=[p.id for p in members],
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[HOAAssociationOut])
def list_associations(
    response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAAssociation).filter(
        HOAAssociation.organization_id == org_id, HOAAssociation.is_active.is_(True),
    ).order_by(HOAAssociation.name, HOAAssociation.id).limit(501).all()
    result = []
    for row in rows:
        members = _members(db, org_id=org_id, actor=current_user, association_id=row.id)
        if current_user.role == UserRole.MANAGER and not members:
            continue
        result.append(_out(row, members))
    return result


@router.get("/{association_id}", response_model=HOAAssociationOut)
def get_association(
    association_id: int, response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user)
    row = _association(db, org_id=org_id, association_id=association_id)
    members = _members(db, org_id=org_id, actor=current_user, association_id=row.id)
    if current_user.role == UserRole.MANAGER and not members:
        raise HTTPException(status_code=404, detail="Association not found.")
    response.headers["Cache-Control"] = "no-store"
    return _out(row, members)


def _archive_property_drafts(
    db: Session, *, org_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    """Do not resurrect a previous staff proposal after a property is relinked."""
    query = db.query(HOAAssessmentProposal).filter(
        HOAAssessmentProposal.organization_id == org_id,
        HOAAssessmentProposal.association_id == association_id,
        HOAAssessmentProposal.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAAssessmentProposal.property_id == property_id)
    for draft in query.all():
        draft.is_active = False
        draft.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor_id,
            entity_type="hoa_assessment_proposal", entity_id=draft.id,
            action=action,
            new_value={"association_id": association_id, "property_id": draft.property_id},
        )


def _archive_staff_observations(
    db: Session, *, org_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    """An unlinked association may not silently restore old staff observations."""
    query = db.query(HOAObservation).filter(
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == association_id,
        HOAObservation.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAObservation.property_id == property_id)
    for note in query.all():
        note.is_active = False
        note.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor_id,
            entity_type="hoa_observation", entity_id=note.id,
            action=action,
            new_value={"association_id": association_id, "property_id": note.property_id},
        )




def _archive_meeting_drafts(
    db: Session, *, org_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    """A later association relink must not reinstate old staff meeting plans."""
    query = db.query(HOAMeetingDraft).filter(
        HOAMeetingDraft.organization_id == org_id,
        HOAMeetingDraft.association_id == association_id,
        HOAMeetingDraft.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAMeetingDraft.property_id == property_id)
    for meeting in query.all():
        archive_meeting_workspace(
            db, organization_id=org_id, association_id=association_id,
            property_id=meeting.property_id, meeting_draft_id=meeting.id,
            actor_id=actor_id, action=action,
        )
        meeting.is_active = False
        meeting.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor_id,
            entity_type="hoa_meeting_draft", entity_id=meeting.id,
            action=action,
            new_value={"association_id": association_id, "property_id": meeting.property_id},
        )




def _archive_arc_intakes(
    db: Session, *, org_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    """Relink must not resurrect obsolete staff ARC intake assumptions."""
    query = db.query(HOAARCIntake).filter(
        HOAARCIntake.organization_id == org_id,
        HOAARCIntake.association_id == association_id,
        HOAARCIntake.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAARCIntake.property_id == property_id)
    for record in query.all():
        record.is_active = False
        record.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor_id,
            entity_type="hoa_arc_intake", entity_id=record.id, action=action,
            new_value={"association_id": association_id, "property_id": record.property_id},
        )



def _archive_governing_evidence(
    db: Session, *, org_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    """Never reactivate an old evidence link when an HOA is relinked."""
    query = db.query(HOAGoverningEvidence).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association_id,
        HOAGoverningEvidence.is_active.is_(True),
    )
    if property_id is not None:
        query = query.filter(HOAGoverningEvidence.property_id == property_id)
    for record in query.all():
        record.is_active = False
        record.updated_by_id = actor_id
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor_id,
            entity_type="hoa_governing_evidence", entity_id=record.id, action=action,
            new_value={"association_id": association_id, "property_id": record.property_id},
        )


def _archive_procedure_cases(
    db: Session, *, org_id: int, association_id: int,
    actor_id: int, action: str, property_id: int | None = None,
) -> None:
    """Unlink/archive invalidates old staff rules and review cases."""
    for model, entity in (
        (HOAProcedurePolicy, "hoa_procedure_policy"),
        (HOAViolationCase, "hoa_violation_case"),
        (HOAReserveAccount, "hoa_reserve_account"),
    ):
        rows = db.query(model).filter(
            model.organization_id == org_id,
            model.association_id == association_id,
            model.is_active.is_(True),
        )
        if property_id is not None:
            rows = rows.filter(model.property_id == property_id)
        for row in rows.all():
            row.is_active = False
            row.updated_by_id = actor_id
            db.flush()
            append_audit_log(
                db, organization_id=org_id, user_id=actor_id,
                entity_type=entity, entity_id=row.id, action=action,
                new_value={"association_id": association_id, "property_id": row.property_id},
            )


def _save(db: Session, *, actor: User, payload: HOAAssociationIn,
          association_id: int | None = None) -> HOAAssociationOut:
    org_id = _access(db, actor, write=True)
    wanted = set(payload.property_ids)
    found = {p.id for p in _visible(db, org_id=org_id, actor=actor).filter(
        Property.id.in_(wanted)
    ).all()} if wanted else set()
    if wanted != found:
        raise HTTPException(status_code=404, detail="Property not found.")
    key = payload.name.casefold()
    duplicate = db.query(HOAAssociation.id).filter(
        HOAAssociation.organization_id == org_id, HOAAssociation.name_key == key,
    )
    if association_id is not None:
        duplicate = duplicate.filter(HOAAssociation.id != association_id)
    if duplicate.first() is not None:
        raise HTTPException(status_code=409, detail="Association name already exists.")
    created = association_id is None
    row = (
        HOAAssociation(organization_id=org_id, created_by_id=actor.id)
        if created else _association(db, org_id=org_id, association_id=association_id)
    )
    if created:
        db.add(row)
    row.name, row.name_key, row.updated_by_id = payload.name, key, actor.id
    try:
        db.flush()
        current = db.query(HOAPropertyMembership).filter(
            HOAPropertyMembership.organization_id == org_id,
            HOAPropertyMembership.association_id == row.id,
        ).all()
        current_ids = {m.property_id for m in current}
        for m in current:
            if m.property_id not in wanted:
                for link in db.query(HOAContactLink).filter(
                    HOAContactLink.organization_id == org_id,
                    HOAContactLink.association_id == row.id,
                    HOAContactLink.property_id == m.property_id,
                    HOAContactLink.is_active.is_(True),
                ).all():
                    link.is_active = False
                    link.updated_by_id = actor.id
                    db.flush()
                    append_audit_log(
                        db, organization_id=org_id, user_id=actor.id,
                        entity_type="hoa_contact_link", entity_id=link.id,
                        action="association_property_unlinked",
                    )
                _archive_property_drafts(
                    db, org_id=org_id, association_id=row.id,
                    actor_id=actor.id, property_id=m.property_id,
                    action="association_property_unlinked",
                )
                _archive_staff_observations(
                    db, org_id=org_id, association_id=row.id,
                    actor_id=actor.id, property_id=m.property_id,
                    action="association_property_unlinked",
                )
                _archive_meeting_drafts(
                    db, org_id=org_id, association_id=row.id,
                    actor_id=actor.id, property_id=m.property_id,
                    action="association_property_unlinked",
                )
                _archive_arc_intakes(
                    db, org_id=org_id, association_id=row.id,
                    actor_id=actor.id, property_id=m.property_id,
                    action="association_property_unlinked",
                )
                _archive_governing_evidence(
                    db, org_id=org_id, association_id=row.id,
                    actor_id=actor.id, property_id=m.property_id,
                    action="association_property_unlinked",
                )
                _archive_procedure_cases(
                    db, org_id=org_id, association_id=row.id,
                    actor_id=actor.id, property_id=m.property_id,
                    action="association_property_unlinked",
                )
                db.delete(m)
        for property_id in sorted(wanted - current_ids):
            db.add(HOAPropertyMembership(
                organization_id=org_id, association_id=row.id, property_id=property_id,
            ))
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor.id,
            entity_type="hoa_association", entity_id=row.id,
            action="created" if created else "updated",
            new_value={"property_ids": sorted(wanted)},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Association update conflicts with an existing record.") from exc
    db.refresh(row)
    return _out(row, _members(db, org_id=org_id, actor=actor, association_id=row.id))


@router.post("", response_model=HOAAssociationOut, status_code=201)
def create_association(
    payload: HOAAssociationIn, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save(db, actor=current_user, payload=payload)


@router.put("/{association_id}", response_model=HOAAssociationOut)
def update_association(
    association_id: int, payload: HOAAssociationIn, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save(db, actor=current_user, payload=payload, association_id=association_id)


@router.delete("/{association_id}", status_code=204)
def archive_association(
    association_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write=True)
    row = _association(db, org_id=org_id, association_id=association_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    for link in db.query(HOAContactLink).filter(
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == row.id,
        HOAContactLink.is_active.is_(True),
    ).all():
        link.is_active = False
        link.updated_by_id = current_user.id
        db.flush()
        append_audit_log(db, organization_id=org_id, user_id=current_user.id,
                         entity_type="hoa_contact_link", entity_id=link.id,
                         action="association_archived")
    _archive_property_drafts(
        db, org_id=org_id, association_id=row.id,
        actor_id=current_user.id, action="association_archived",
    )
    _archive_staff_observations(
        db, org_id=org_id, association_id=row.id,
        actor_id=current_user.id, action="association_archived",
    )
    _archive_meeting_drafts(
        db, org_id=org_id, association_id=row.id,
        actor_id=current_user.id, action="association_archived",
    )
    _archive_arc_intakes(
        db, org_id=org_id, association_id=row.id,
        actor_id=current_user.id, action="association_archived",
    )
    _archive_governing_evidence(
        db, org_id=org_id, association_id=row.id,
        actor_id=current_user.id, action="association_archived",
    )
    _archive_procedure_cases(
        db, org_id=org_id, association_id=row.id,
        actor_id=current_user.id, action="association_archived",
    )
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_association", entity_id=row.id,
        action="archived",
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})



def _contact_scope(
    db: Session, *, actor: User, association_id: int,
    property_id: int, write: bool,
) -> tuple[int, HOAAssociation]:
    org_id = _access(db, actor, write=write)
    if not permission_allows_user(db, user=actor, menu_key="PEOPLE.CONTACTS"):
        raise HTTPException(status_code=403, detail="Contacts permission required.")
    association = _association(db, org_id=org_id, association_id=association_id)
    prop = _visible(db, org_id=org_id, actor=actor).filter(Property.id == property_id).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Association property not found.")
    linked = db.query(HOAPropertyMembership.id).filter(
        HOAPropertyMembership.organization_id == org_id,
        HOAPropertyMembership.association_id == association.id,
        HOAPropertyMembership.property_id == prop.id,
    ).first()
    if linked is None:
        raise HTTPException(status_code=404, detail="Association property not found.")
    return org_id, association


def _contact(db: Session, *, org_id: int, contact_id: int) -> Contact:
    row = db.query(Contact).filter(
        Contact.id == contact_id, Contact.organization_id == org_id,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return row


@router.get("/{association_id}/contacts", response_model=list[HOAContactLinkOut])
def list_contact_links(
    association_id: int, property_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """View only staff references within this currently visible association property."""
    org_id, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAContactLink, Contact).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).filter(
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association.id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org_id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).order_by(Contact.display_name, HOAContactLink.id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many recorded contacts for one property.")
    return [
        HOAContactLinkOut(id=link.id, association_id=association.id,
                          property_id=property_id, contact_id=contact.id,
                          contact_name=contact.display_name)
        for link, contact in rows
    ]


@router.post("/{association_id}/contacts", response_model=HOAContactLinkOut, status_code=201)
def add_contact_link(
    association_id: int, payload: HOAContactLinkIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    contact = _contact(db, org_id=org_id, contact_id=payload.contact_id)
    link = db.query(HOAContactLink).filter(
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association.id,
        HOAContactLink.property_id == payload.property_id,
        HOAContactLink.contact_id == contact.id,
    ).first()
    if link is not None and link.is_active:
        raise HTTPException(status_code=409, detail="Contact already recorded for this property.")
    created = link is None
    if created:
        link = HOAContactLink(
            organization_id=org_id, association_id=association.id,
            property_id=payload.property_id, contact_id=contact.id,
            created_by_id=current_user.id,
        )
        db.add(link)
    else:
        link.is_active = True
    link.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_contact_link", entity_id=link.id,
            action="created" if created else "restored",
            new_value={"association_id": association.id, "property_id": payload.property_id,
                       "contact_id": contact.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Contact link was updated concurrently.") from exc
    db.refresh(link)
    return HOAContactLinkOut(id=link.id, association_id=association.id,
                             property_id=payload.property_id,
                             contact_id=contact.id, contact_name=contact.display_name)


@router.delete("/{association_id}/contacts/{link_id}", status_code=204)
def remove_contact_link(
    association_id: int, link_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    link = db.query(HOAContactLink).filter(
        HOAContactLink.id == link_id, HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association.id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
    ).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Contact link not found.")
    link.is_active = False
    link.updated_by_id = current_user.id
    archive_contact_participation(
        db, organization_id=org_id, association_id=association.id,
        property_id=property_id, contact_link_id=link.id,
        actor_id=current_user.id, action="contact_link_archived",
    )
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_contact_link", entity_id=link.id, action="archived",
        new_value={"association_id": association.id, "property_id": property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
