"""Explicit staff-entered dated inspection entries, append-only workflow."""
from __future__ import annotations

from typing import Annotated, Literal
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from app.models.entity_attachment import EntityAttachment
from app.models.audit_log import AuditLog
from app.models.unit_inspection import UnitInspectionRecord, UnitInspectionReview
from app.services.attachment_storage import attachment_path
from app.services.audit import append_audit_log

from app.core.database import get_db
from app.models.user import User
from app.models.property import Property, Unit
from app.models.work_order import WorkOrder
from app.schemas.work_order import WorkOrderOut
from app.routers.auth import get_current_user
from app.schemas.unit_inspection import (UnitInspectionCreateIn, UnitInspectionOut,
    InspectionReviewIn, InspectionReviewOut)
from app.services.report_delivery import ReportDeliveryError
from app.services.unit_inspections import (get_inspection, list_inspections, record_inspection,
    get_inspection_review, independently_review_inspection)

router = APIRouter(prefix="/api/unit-inspections", tags=["Unit Inspection Records"])

# Private inspection evidence is intentionally distinct from generic shareable attachments.
# Content-derived keys provide exact-upload replay without creating duplicate immutable rows.
_INSPECTION_MIME = {
    "image/jpeg": (bytes.fromhex("ffd8ff"),),
    "image/png": (bytes.fromhex("89504e470d0a1a0a"),),
    "image/webp": (b"RIFF",),
}
_MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _verified_photo_bytes(row: EntityAttachment) -> bytes:
    expected = row.storage_key.removesuffix(Path(row.storage_key).suffix).split("-")[-1]
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise HTTPException(status_code=409, detail="Invalid photo evidence checksum")
    path = attachment_path(row.storage_key)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=409, detail="Photo evidence bytes unavailable") from exc
    if len(data) != row.size_bytes or sha256(data).hexdigest() != expected:
        raise HTTPException(status_code=409, detail="Photo evidence integrity check failed")
    return data


def _photo_info(db: Session, inspection_id: int, actor: User):
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        record = get_inspection(db, actor=actor, inspection_id=inspection_id)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc
    return record


def _photo_list(db: Session, inspection_id: int, actor: User):
    record = _photo_info(db, inspection_id, actor)
    return db.query(EntityAttachment).filter(
        EntityAttachment.organization_id == actor.organization_id,
        EntityAttachment.entity_type == "unit_inspection_records",
        EntityAttachment.entity_id == record.id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).order_by(EntityAttachment.id.asc()).limit(100).all()


@router.get("/{inspection_id}/photos")
def list_inspection_photos(inspection_id: int,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    return [{"id": x.id, "original_name": x.original_name, "size_bytes": x.size_bytes,
             "created_at": x.created_at} for x in _photo_list(db, inspection_id, current_user)]


@router.get("/{inspection_id}/photos/{photo_id}")
def download_inspection_photo(inspection_id: int, photo_id: int,
                              db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    row = next((x for x in _photo_list(db, inspection_id, current_user) if x.id == photo_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Inspection photo not found")
    data = _verified_photo_bytes(row)
    return Response(content=data, media_type=row.content_type,
                    headers={"Cache-Control": "private, no-store",
                             "Content-Disposition": f'attachment; filename="inspection-{row.id}"'})


@router.get("/{inspection_id}/photo-manifest")
def read_sealed_inspection_photo_manifest(inspection_id: int,
                                           db: Session = Depends(get_db),
                                           current_user: User = Depends(get_current_user)):
    """Frozen review-time evidence list; never infer reviewed photos from later data."""
    record = _photo_info(db, inspection_id, current_user)
    reviewed = db.query(UnitInspectionReview).filter(
        UnitInspectionReview.inspection_id == record.id,
        UnitInspectionReview.organization_id == current_user.organization_id,
    ).first()
    if reviewed is None:
        return {"sealed": False, "photos": []}
    audit = db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id,
        AuditLog.entity_type == "unit_inspection_review",
        AuditLog.entity_id == reviewed.id,
        AuditLog.action == "independent_review_recorded",
    ).one_or_none()
    if audit is None:
        raise HTTPException(status_code=409, detail="Sealed inspection evidence manifest unavailable")
    try:
        snapshot = json.loads(audit.new_value or "{}")
        ids, hashes = snapshot["photo_evidence_ids"], snapshot["photo_evidence_hashes"]
        if (not isinstance(ids, list) or not isinstance(hashes, list) or len(ids) != len(hashes)
                or len(ids) > 100 or len(set(ids)) != len(ids)
                or any(not isinstance(i, int) or i < 1 for i in ids)
                or any(not isinstance(h, str) or len(h) != 64
                       or any(ch not in "0123456789abcdef" for ch in h) for h in hashes)):
            raise ValueError("Invalid manifest")
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=409, detail="Sealed inspection evidence manifest invalid") from exc
    rows = {row.id: row for row in _photo_list(db, record.id, current_user)}
    photos = []
    for photo_id, digest in zip(ids, hashes):
        row = rows.get(photo_id)
        present = bool(row is not None and row.storage_key.split("-")[-1].split(".")[0] == digest)
        intact = False
        if present:
            try:
                _verified_photo_bytes(row)
                intact = True
            except HTTPException:
                intact = False
        photos.append({"id": photo_id, "sha256": digest,
                       "original_name": row.original_name if present else None,
                       "record_present": present, "bytes_verified": intact})
    return {"sealed": True, "photos": photos}


@router.post("/{inspection_id}/photos", status_code=201)
async def upload_inspection_photo(inspection_id: int, file: UploadFile = File(...),
                                  db: Session = Depends(get_db),
                                  current_user: User = Depends(get_current_user)):
    # Reject tenant, cross-company, revoked membership and retired inventory
    # using the exact inspection scope before reading untrusted bytes.
    record = _photo_info(db, inspection_id, current_user)
    mime = file.content_type or ""
    if mime not in _INSPECTION_MIME:
        raise HTTPException(status_code=422, detail="JPEG, PNG or WebP photo required")
    data = await file.read(_MAX_PHOTO_BYTES + 1)
    if not data or len(data) > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo must be 1 byte to 10 MB")
    if not data.startswith(_INSPECTION_MIME[mime][0]):
        raise HTTPException(status_code=422, detail="Photo content does not match declared type")
    if mime == "image/webp" and (len(data) < 12 or data[8:12] != b"WEBP"):
        raise HTTPException(status_code=422, detail="Invalid WebP photo")
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
    key = "inspection-%d-%d-%s%s" % (
        current_user.organization_id, record.id, sha256(data).hexdigest(), suffix)
    filename = Path(file.filename or "inspection-photo").name[:255]
    if not filename or filename in {".", ".."}:
        filename = "inspection-photo" + suffix
    if Path(filename).suffix.lower() not in ({".jpg", ".jpeg"} if mime == "image/jpeg" else {suffix}):
        raise HTTPException(status_code=422, detail="Photo filename extension does not match content type")
    locked = db.query(UnitInspectionRecord).filter(
        UnitInspectionRecord.id == record.id,
        UnitInspectionRecord.organization_id == current_user.organization_id,
    ).with_for_update().one()
    # Recheck authorization under lock before committing immutable evidence.
    _photo_info(db, locked.id, current_user)
    active_unit = db.query(Unit.id).join(Property, Property.id == Unit.property_id).filter(
        Unit.id == locked.unit_id, Unit.property_id == locked.property_id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        Property.organization_id == current_user.organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).first()
    if active_unit is None:
        raise HTTPException(status_code=409, detail="Retired inventory cannot receive new photos")
    existing = db.query(EntityAttachment).filter_by(storage_key=key).first()
    if existing is not None:
        if (existing.entity_id != locked.id or existing.organization_id != current_user.organization_id
                or not existing.is_active):
            raise HTTPException(status_code=409, detail="Photo evidence key conflict")
        _verified_photo_bytes(existing)
        return {"id": existing.id, "original_name": existing.original_name,
                "size_bytes": existing.size_bytes, "created_at": existing.created_at}
    if db.query(UnitInspectionReview.id).filter_by(inspection_id=locked.id).first():
        raise HTTPException(status_code=409, detail="Reviewed inspection evidence is sealed")
    count = db.query(EntityAttachment).filter(
        EntityAttachment.organization_id == current_user.organization_id,
        EntityAttachment.entity_type == "unit_inspection_records",
        EntityAttachment.entity_id == locked.id,
        EntityAttachment.is_active.is_(True),
    ).count()
    if count >= 100:
        raise HTTPException(status_code=409, detail="Inspection photo evidence limit reached")
    path = attachment_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    created_bytes = False
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if path.read_bytes() != data:
            raise HTTPException(status_code=409, detail="Photo storage integrity conflict")
    else:
        created_bytes = True
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
    item = EntityAttachment(
        organization_id=current_user.organization_id,
        entity_type="unit_inspection_records", entity_id=locked.id, storage_key=key,
        original_name=filename, content_type=mime, size_bytes=len(data),
        share_with_owners=False, share_with_tenants=False,
        uploaded_by_id=current_user.id, is_active=True,
    )
    try:
        db.add(item)
        db.flush()
        append_audit_log(db, organization_id=current_user.organization_id,
                         user_id=current_user.id,
                         entity_type="unit_inspection_photo", entity_id=item.id,
                         action="evidence_uploaded",
                         new_value={"inspection_id": locked.id, "sha256": sha256(data).hexdigest(),
                                    "size_bytes": len(data), "mime": mime})
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        replay = db.query(EntityAttachment).filter_by(storage_key=key).first()
        if replay is None:
            raise
        _verified_photo_bytes(replay)
        item = replay
    except Exception:
        # Leave the content-hashed bytes for an exact safe replay, but never
        # leave an uncommitted attachment or audit record in the session.
        db.rollback()
        raise
    return {"id": item.id, "original_name": item.original_name,
            "size_bytes": item.size_bytes, "created_at": item.created_at}




def _error(exc: ReportDeliveryError) -> HTTPException:
    message = str(exc)
    if "permission" in message:
        return HTTPException(status_code=403, detail=message)
    if "not found" in message:
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=422, detail=message)


@router.get("", response_model=list[UnitInspectionOut])
def get_inspections(
    response: Response,
    property_id: int | None = Query(default=None, ge=1),
    unit_id: int | None = Query(default=None, ge=1),
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    recorded_condition: Literal["SATISFACTORY", "ATTENTION_NEEDED", "NOT_ASSESSED"] | None = None,
    review_state: Literal["PENDING", "REVIEWED"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from cannot be after date_to")
    try:
        return list_inspections(
            db, actor=current_user, property_id=property_id, unit_id=unit_id,
            limit=limit, offset=offset,
            recorded_condition=recorded_condition, review_state=review_state,
            date_from=date_from, date_to=date_to,
        )
    except ReportDeliveryError as exc:
        raise _error(exc) from exc



@router.get("/{inspection_id}", response_model=UnitInspectionOut)
def get_inspection_detail(
    inspection_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        return get_inspection(db, actor=current_user, inspection_id=inspection_id)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc



@router.get("/{inspection_id}/work-orders", response_model=list[WorkOrderOut])
def get_inspection_work_orders(
    inspection_id: int,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read linked follow-ups only after authorizing the exact inspection."""
    response.headers["Cache-Control"] = "no-store"
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        inspection = get_inspection(
            db, actor=current_user, inspection_id=inspection_id,
        )
    except ReportDeliveryError as exc:
        raise _error(exc) from exc
    # Defensive parent reconciliation also covers manually corrupted links.
    return db.query(WorkOrder).join(
        Unit, Unit.id == WorkOrder.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).filter(
        WorkOrder.source_inspection_id == inspection.id,
        WorkOrder.unit_id == inspection.unit_id,
        WorkOrder.property_id == inspection.property_id,
        Property.id == inspection.property_id,
        Property.organization_id == current_user.organization_id,
    ).order_by(WorkOrder.id.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=UnitInspectionOut, status_code=201)
def create_inspection(
    payload: UnitInspectionCreateIn,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return record_inspection(db, actor=current_user, payload=payload)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc

@router.get("/{inspection_id}/review", response_model=InspectionReviewOut | None)
def read_inspection_review(
    inspection_id: int, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        return get_inspection_review(db, actor=current_user, inspection_id=inspection_id)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc


@router.post("/{inspection_id}/review", response_model=InspectionReviewOut, status_code=201)
def review_inspection(
    inspection_id: int, payload: InspectionReviewIn, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        return independently_review_inspection(
            db, actor=current_user, inspection_id=inspection_id, payload=payload,
        )
    except ReportDeliveryError as exc:
        raise _error(exc) from exc
