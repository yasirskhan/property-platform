"""Property-scoped staff tour/guest cards linked to authorized CRM prospects.

Not public signup, a lease/application submission, or consent/e-signature.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.guest_card import GuestCard
from app.models.property import Unit
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.prospects import _access, _row as _prospect, _visible as _visible_prospects
from app.schemas.guest_card import GuestCardIn, GuestCardUpdate, GuestCardOut, GuestCardList
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/leasing/guest-cards", tags=["Leasing Guest Cards"])


def _unit(db: Session, *, property_id: int, unit_id: int | None) -> None:
    if unit_id is None:
        return
    exists = db.query(Unit.id).filter(
        Unit.id == unit_id, Unit.property_id == property_id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
    ).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Unit not found.")


def _card(db: Session, *, user: User, card_id: int, write: bool = False):
    org = _access(db, user, write=write)
    card = db.query(GuestCard).filter(
        GuestCard.id == card_id, GuestCard.organization_id == org,
        GuestCard.is_active.is_(True),
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="Guest card not found.")
    prospect = _prospect(db, org, user, card.prospect_id)
    return card, prospect


def _out(card: GuestCard, prospect) -> GuestCardOut:
    # _prospect guarantees current organization/property/contact visibility.
    return GuestCardOut(
        id=card.id, organization_id=card.organization_id,
        prospect_id=card.prospect_id, property_id=prospect.property_id,
        contact_name=prospect_contact_name_placeholder(prospect),
        visit_on=card.visit_on, unit_id=card.unit_id, attended=card.attended,
        next_step=card.next_step, is_active=card.is_active,
        created_at=card.created_at, updated_at=card.updated_at,
    )


def prospect_contact_name_placeholder(prospect) -> str:
    # Replaced by scoped Contact lookup in _view; no raw user input is trusted.
    return str(prospect.contact_id)


def _view(db: Session, card: GuestCard, prospect) -> GuestCardOut:
    from app.models.contact import Contact
    person = db.query(Contact.display_name).filter(
        Contact.id == prospect.contact_id,
        Contact.organization_id == prospect.organization_id,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
    ).first()
    if person is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    result = _out(card, prospect)
    return result.model_copy(update={"contact_name": person[0]})


@router.get("", response_model=GuestCardList)
def list_guest_cards(
    response: Response, prospect_id: int | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    if prospect_id is not None:
        _prospect(db, org, current_user, prospect_id)
    visible_ids = _visible_prospects(db, org, current_user).with_entities(
        __import__("app.models.prospect", fromlist=["Prospect"]).Prospect.id
    )
    q = db.query(GuestCard).filter(
        GuestCard.organization_id == org, GuestCard.is_active.is_(True),
        GuestCard.prospect_id.in_(visible_ids),
    )
    if prospect_id is not None:
        q = q.filter(GuestCard.prospect_id == prospect_id)
    cards = q.order_by(GuestCard.visit_on.desc(), GuestCard.id.desc()).limit(201).all()
    if len(cards) > 200:
        raise HTTPException(status_code=422, detail="Narrow guest-card list.")
    items = []
    for card in cards:
        try:
            prospect = _prospect(db, org, current_user, card.prospect_id)
            items.append(_view(db, card, prospect))
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    return GuestCardList(items=items, total=len(items))


@router.post("", response_model=GuestCardOut, status_code=201)
def create_guest_card(
    payload: GuestCardIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user, write=True)
    prospect = _prospect(db, org, current_user, payload.prospect_id)
    _unit(db, property_id=prospect.property_id, unit_id=payload.unit_id)
    if db.query(GuestCard.id).filter(
        GuestCard.organization_id == org, GuestCard.prospect_id == prospect.id,
        GuestCard.visit_on == payload.visit_on,
    ).first():
        raise HTTPException(status_code=409, detail="Guest card already recorded for this prospect and day.")
    row = GuestCard(
        organization_id=org, created_by_id=current_user.id,
        updated_by_id=current_user.id, **payload.model_dump(),
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(db, user_id=current_user.id, organization_id=org,
                         entity_type="leasing_guest_card", entity_id=row.id, action="created",
                         new_value={"prospect_id": row.prospect_id, "visit_on": row.visit_on.isoformat()})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Guest card already recorded for this prospect and day.") from exc
    db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return _view(db, row, prospect)


@router.patch("/{card_id}", response_model=GuestCardOut)
def update_guest_card(
    card_id: int, payload: GuestCardUpdate, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    card, prospect = _card(db, user=current_user, card_id=card_id, write=True)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No changes supplied.")
    if ("attended" in changes and changes["attended"] is None or
        "next_step" in changes and changes["next_step"] is None):
        raise HTTPException(status_code=422, detail="Attendance and next step cannot be blank.")
    if "unit_id" in changes:
        _unit(db, property_id=prospect.property_id, unit_id=changes["unit_id"])
    changed = []
    for key, value in changes.items():
        if getattr(card, key) != value:
            setattr(card, key, value)
            changed.append(key)
    if changed:
        card.updated_by_id = current_user.id
        db.flush()
        append_audit_log(db, user_id=current_user.id, organization_id=card.organization_id,
                         entity_type="leasing_guest_card", entity_id=card.id,
                         action="updated", field_name=",".join(sorted(changed)),
                         new_value={"changed_fields": sorted(changed)})
        db.commit()
    db.refresh(card)
    response.headers["Cache-Control"] = "no-store"
    return _view(db, card, prospect)


@router.delete("/{card_id}", status_code=204)
def archive_guest_card(
    card_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    card, _ = _card(db, user=current_user, card_id=card_id, write=True)
    card.is_active = False
    append_audit_log(db, user_id=current_user.id, organization_id=card.organization_id,
                     entity_type="leasing_guest_card", entity_id=card.id, action="archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
