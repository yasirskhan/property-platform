"""Universal attachment API for organization-scoped business entities."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.entity_attachment import (
    EntityAttachmentListOut,
    EntityAttachmentOut,
    EntityAttachmentShareUpdate,
)
from app.services.attachment_storage import (
    attachment_path,
    remove_attachment_bytes,
    store_attachment_bytes,
)
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.entity_notes import resolve_note_target


router = APIRouter(prefix="/api/attachments", tags=["Entity Attachments"])
ATTACHMENTS_FEATURE_KEY = "release.documents.attachments"


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def _require_feature(db: Session, current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    decision = next(
        (item for item in resolve_customer_features(db, user=current_user) if item.key == ATTACHMENTS_FEATURE_KEY),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Attachments are not available.")
    return int(current_user.organization_id)


def _out(db: Session, row: EntityAttachment) -> EntityAttachmentOut:
    uploader_name = None
    if row.uploaded_by_id is not None:
        uploader = db.query(User).filter(User.id == row.uploaded_by_id).first()
        if uploader is not None:
            uploader_name = f"{uploader.first_name} {uploader.last_name}".strip() or None
    return EntityAttachmentOut(
        id=row.id,
        organization_id=row.organization_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        original_name=row.original_name,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        share_with_tenants=bool(row.share_with_tenants),
        share_with_owners=bool(row.share_with_owners),
        uploaded_by_id=row.uploaded_by_id,
        uploaded_by_name=uploader_name,
        created_at=row.created_at,
    )


def _attachment_for_user(db: Session, *, attachment_id: int, current_user: User) -> EntityAttachment:
    organization_id = _require_feature(db, current_user)
    row = (
        db.query(EntityAttachment)
        .filter(
            EntityAttachment.id == attachment_id,
            EntityAttachment.organization_id == organization_id,
            EntityAttachment.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    resolve_note_target(
        db,
        current_user=current_user,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
    )
    return row


@router.get("/download/{attachment_id}")
def download_entity_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _attachment_for_user(db, attachment_id=attachment_id, current_user=current_user)
    try:
        path = attachment_path(row.storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Attachment file not found.") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found.")
    return FileResponse(
        path,
        media_type=row.content_type or "application/octet-stream",
        filename=row.original_name,
    )


@router.patch("/item/{attachment_id}", response_model=EntityAttachmentOut)
def update_entity_attachment_sharing(
    attachment_id: int,
    payload: EntityAttachmentShareUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _attachment_for_user(db, attachment_id=attachment_id, current_user=current_user)
    if _role(current_user) not in {"ADMIN", "OWNER", "MANAGER"}:
        raise HTTPException(status_code=403, detail="Manager access required.")
    if payload.share_with_tenants is None and payload.share_with_owners is None:
        raise HTTPException(status_code=400, detail="No sharing change supplied.")

    old_value = {
        "share_with_tenants": bool(row.share_with_tenants),
        "share_with_owners": bool(row.share_with_owners),
    }
    if payload.share_with_tenants is not None:
        row.share_with_tenants = payload.share_with_tenants
    if payload.share_with_owners is not None:
        row.share_with_owners = payload.share_with_owners
    new_value = {
        "share_with_tenants": bool(row.share_with_tenants),
        "share_with_owners": bool(row.share_with_owners),
    }
    if old_value != new_value:
        append_audit_log(
            db,
            user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action="attachment_sharing_updated",
            field_name="attachment_sharing",
            old_value={"attachment_id": row.id, **old_value},
            new_value={"attachment_id": row.id, **new_value},
        )
    db.commit()
    db.refresh(row)
    return _out(db, row)


@router.delete("/item/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _attachment_for_user(db, attachment_id=attachment_id, current_user=current_user)
    role = _role(current_user)
    if role not in {"ADMIN", "OWNER", "MANAGER"} and row.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to remove this attachment.")
    row.is_active = False
    row.deleted_at = datetime.utcnow()
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=row.organization_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        action="attachment_removed",
        new_value={"attachment_id": row.id, "filename": row.original_name},
    )
    db.commit()
    return None


@router.get("/{entity_type}/{entity_id}", response_model=EntityAttachmentListOut)
def list_entity_attachments(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_feature(db, current_user)
    clean, _, org_id = resolve_note_target(
        db,
        current_user=current_user,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    rows = (
        db.query(EntityAttachment)
        .filter(
            EntityAttachment.organization_id == org_id,
            EntityAttachment.entity_type == clean,
            EntityAttachment.entity_id == entity_id,
            EntityAttachment.is_active.is_(True),
        )
        .order_by(EntityAttachment.created_at.desc(), EntityAttachment.id.desc())
        .all()
    )
    return EntityAttachmentListOut(items=[_out(db, row) for row in rows], total=len(rows))


@router.post("/{entity_type}/{entity_id}", response_model=EntityAttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_entity_attachment(
    entity_type: str,
    entity_id: int,
    file: UploadFile = File(...),
    share_with_tenants: bool = Form(False),
    share_with_owners: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_feature(db, current_user)
    clean, _, org_id = resolve_note_target(
        db,
        current_user=current_user,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    if (share_with_tenants or share_with_owners) and _role(current_user) not in {"ADMIN", "OWNER", "MANAGER"}:
        raise HTTPException(status_code=403, detail="Manager access required to share attachments.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum is {settings.MAX_UPLOAD_MB} MB")
    try:
        storage_key, original_name = store_attachment_bytes(filename=file.filename, contents=contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = EntityAttachment(
        organization_id=org_id,
        entity_type=clean,
        entity_id=entity_id,
        storage_key=storage_key,
        original_name=original_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(contents),
        share_with_tenants=share_with_tenants,
        share_with_owners=share_with_owners,
        uploaded_by_id=current_user.id,
        is_active=True,
    )
    try:
        db.add(row)
        db.flush()
        append_audit_log(
            db,
            user_id=current_user.id,
            organization_id=org_id,
            entity_type=clean,
            entity_id=entity_id,
            action="attachment_added",
            new_value={"attachment_id": row.id, "filename": row.original_name, "size_bytes": row.size_bytes},
        )
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        remove_attachment_bytes(storage_key)
        raise
    return _out(db, row)
