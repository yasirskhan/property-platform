"""Universal tags: allowed entity targets only, live entity authorization, immutable audits."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tag import Tag, EntityTag
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.tag import TagCreate, TagUpdate, TagListOut, TagOut
from app.services.audit import append_audit_log
from app.services.entity_notes import resolve_note_target
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/tags", tags=["Universal Tags"])

# Explicit allowlist. Generic introspection alone is not enough; no
# financial metadata, authentication, tax, billing or platform targets.
TAGGABLE = frozenset((
    "contacts", "vendors", "properties", "units",
    "leases", "work_orders", "bills", "owner_statements",
))


def _access(db: Session, user: User, *, write_definition: bool = False) -> int:
    roles = {UserRole.ADMIN} if write_definition else {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
    if (
        user.organization_id is None or not user.is_active
        or user.deleted_at is not None or user.role not in roles
        or not permission_allows_user(db, user=user, menu_key="PEOPLE.CONTACTS")
    ):
        raise HTTPException(status_code=403, detail="Tag permission required.")
    return int(user.organization_id)


def _target(db: Session, *, user: User, kind: str, entity_id: int) -> tuple[str, int]:
    org_id = _access(db, user)
    # Fail before ORM introspection on all non-approved targets.
    if kind not in TAGGABLE or entity_id <= 0:
        raise HTTPException(status_code=404, detail="Tag target not available.")
    # Vendor directory is ADMIN/OWNER only even though general notes
    # permission may be broader for managers.
    if kind == "vendors" and user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Vendor scope required.")
    clean, _, target_org = resolve_note_target(
        db, current_user=user, entity_type=kind, entity_id=entity_id,
    )
    if target_org != org_id:
        raise HTTPException(status_code=404, detail="Tag target not found.")
    return clean, org_id


def _tag(db: Session, *, org_id: int, tag_id: int) -> Tag:
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.organization_id == org_id).first()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found.")
    return tag


@router.get("", response_model=TagListOut)
def list_tags(
    response: Response,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    q = db.query(Tag).filter(Tag.organization_id == org_id)
    if not include_inactive:
        q = q.filter(Tag.is_active.is_(True))
    rows = q.order_by(Tag.name.asc(), Tag.id.asc()).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Narrow tag vocabulary before listing.")
    return TagListOut(items=rows, total=len(rows))


@router.post("", response_model=TagOut, status_code=201)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write_definition=True)
    normalized = payload.name.casefold()
    if db.query(Tag.id).filter(Tag.organization_id == org_id, Tag.normalized_name == normalized).first():
        raise HTTPException(status_code=409, detail="Tag name already exists.")
    row = Tag(
        organization_id=org_id, name=payload.name,
        normalized_name=normalized, created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tag name already exists.") from exc
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="tag", entity_id=row.id, action="created",
    )
    db.commit(); db.refresh(row)
    return row


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int, payload: TagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write_definition=True)
    row = _tag(db, org_id=org_id, tag_id=tag_id)
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Restore tag before renaming.")
    normalized = payload.name.casefold()
    if normalized == row.normalized_name and payload.name == row.name:
        return row
    duplicate = db.query(Tag.id).filter(
        Tag.organization_id == org_id, Tag.normalized_name == normalized,
        Tag.id != row.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Tag name already exists.")
    row.name, row.normalized_name, row.updated_by_id = payload.name, normalized, current_user.id
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tag name already exists.") from exc
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="tag", entity_id=row.id, action="updated",
        field_name="name",
    )
    db.commit(); db.refresh(row)
    return row


@router.delete("/{tag_id}", status_code=204)
def deactivate_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write_definition=True)
    row = _tag(db, org_id=org_id, tag_id=tag_id)
    if row.is_active:
        row.is_active, row.updated_by_id = False, current_user.id
        db.flush()
        append_audit_log(db, user_id=current_user.id, organization_id=org_id,
                         entity_type="tag", entity_id=row.id, action="deactivated")
        db.commit()
    return Response(status_code=204)


@router.post("/{tag_id}/restore", response_model=TagOut)
def restore_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write_definition=True)
    row = _tag(db, org_id=org_id, tag_id=tag_id)
    if not row.is_active:
        row.is_active, row.updated_by_id = True, current_user.id
        db.flush()
        append_audit_log(db, user_id=current_user.id, organization_id=org_id,
                         entity_type="tag", entity_id=row.id, action="restored")
        db.commit()
    db.refresh(row)
    return row


@router.get("/target/{entity_type}/{entity_id}", response_model=TagListOut)
def list_target_tags(
    entity_type: str, entity_id: int, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean, org_id = _target(db, user=current_user, kind=entity_type, entity_id=entity_id)
    response.headers["Cache-Control"] = "no-store"
    rows = (
        db.query(Tag)
        .join(EntityTag, EntityTag.tag_id == Tag.id)
        .filter(
            EntityTag.organization_id == org_id, Tag.organization_id == org_id,
            EntityTag.entity_type == clean, EntityTag.entity_id == entity_id,
        )
        .order_by(Tag.name.asc(), Tag.id.asc()).limit(501).all()
    )
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many target tags.")
    return TagListOut(items=rows, total=len(rows))


@router.post("/target/{entity_type}/{entity_id}/{tag_id}", response_model=TagOut)
def assign_tag(
    entity_type: str, entity_id: int, tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean, org_id = _target(db, user=current_user, kind=entity_type, entity_id=entity_id)
    row = _tag(db, org_id=org_id, tag_id=tag_id)
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Inactive tag cannot be assigned.")
    exists = db.query(EntityTag).filter(
        EntityTag.organization_id == org_id,
        EntityTag.tag_id == tag_id,
        EntityTag.entity_type == clean, EntityTag.entity_id == entity_id,
    ).first()
    if exists is not None:
        return row
    link = EntityTag(
        organization_id=org_id, tag_id=tag_id, entity_type=clean,
        entity_id=entity_id, created_by_id=current_user.id,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tag already assigned.")
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type=clean, entity_id=entity_id, action="tag_added",
        new_value={"tag_id": tag_id},
    )
    db.commit()
    return row


@router.delete("/target/{entity_type}/{entity_id}/{tag_id}", status_code=204)
def unassign_tag(
    entity_type: str, entity_id: int, tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean, org_id = _target(db, user=current_user, kind=entity_type, entity_id=entity_id)
    _tag(db, org_id=org_id, tag_id=tag_id)
    link = db.query(EntityTag).filter(
        EntityTag.organization_id == org_id,
        EntityTag.tag_id == tag_id,
        EntityTag.entity_type == clean, EntityTag.entity_id == entity_id,
    ).first()
    if link is not None:
        db.delete(link)
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type=clean, entity_id=entity_id, action="tag_removed",
            old_value={"tag_id": tag_id},
        )
        db.commit()
    return Response(status_code=204)
