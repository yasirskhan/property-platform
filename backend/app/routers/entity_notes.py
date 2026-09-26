"""Universal timestamped notes API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_note import EntityNote
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.entity_note import EntityNoteCreateIn, EntityNoteListOut, EntityNoteOut
from app.services.audit import append_audit_log
from app.services.entity_notes import resolve_note_target


router = APIRouter(prefix="/api/notes", tags=["Entity Notes"])


def _out(db: Session, note: EntityNote) -> EntityNoteOut:
    creator_name = None
    if note.created_by_id is not None:
        creator = db.query(User).filter(User.id == note.created_by_id).first()
        if creator is not None:
            creator_name = f"{creator.first_name} {creator.last_name}".strip()
    return EntityNoteOut(
        id=note.id,
        organization_id=note.organization_id,
        entity_type=note.entity_type,
        entity_id=note.entity_id,
        body=note.body,
        created_by_id=note.created_by_id,
        created_by_name=creator_name or None,
        created_at=note.created_at,
    )


@router.get("/{entity_type}/{entity_id}", response_model=EntityNoteListOut)
def list_entity_notes(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean, _, org_id = resolve_note_target(
        db,
        current_user=current_user,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    rows = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == org_id,
            EntityNote.entity_type == clean,
            EntityNote.entity_id == entity_id,
        )
        .order_by(EntityNote.created_at.desc(), EntityNote.id.desc())
        .all()
    )
    return EntityNoteListOut(items=[_out(db, row) for row in rows], total=len(rows))


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=EntityNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def add_entity_note(
    entity_type: str,
    entity_id: int,
    payload: EntityNoteCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean, _, org_id = resolve_note_target(
        db,
        current_user=current_user,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    note = EntityNote(
        organization_id=org_id,
        entity_type=clean,
        entity_id=entity_id,
        body=payload.body,
        created_by_id=current_user.id,
    )
    db.add(note)
    db.flush()
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=org_id,
        entity_type=clean,
        entity_id=entity_id,
        action="note_added",
        new_value={"note_id": note.id},
    )
    db.commit()
    db.refresh(note)
    return _out(db, note)
