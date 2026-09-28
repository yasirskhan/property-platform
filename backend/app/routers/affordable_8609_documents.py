"""Raw PDF body, never multipart/plaintext spool, for restricted 8609 archive."""
from __future__ import annotations
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.affordable_8609_document import Affordable8609DocumentOut
from app.services.affordable_8609_documents import (
    MAX_8609_BYTES, _scope, archive_8609, download_8609, list_8609, rotate_building_scans,
)

router = APIRouter(prefix="/api/properties", tags=["Restricted Form 8609 scans"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


@router.get("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-documents",
            response_model=list[Affordable8609DocumentOut])
def list_documents(
    property_id: int, program_id: int, building_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return list_8609(db, property_id=property_id, program_id=program_id,
                     building_id=building_id, current_user=current_user)


@router.post("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-documents",
             response_model=Affordable8609DocumentOut, status_code=201)
async def upload_document(
    property_id: int, program_id: int, building_id: int, request: Request, response: Response,
    received_on: date = Query(...), signed_copy_reviewed: bool = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    # Check actor and scope before reading the sensitive request body.
    _scope(db, property_id=property_id, program_id=program_id,
           building_id=building_id, user=current_user, write=True)
    if request.headers.get("content-type", "").split(";", 1)[0].lower().strip() != "application/pdf":
        raise HTTPException(status_code=415, detail="Send a PDF as application/pdf.")
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid content length.")
        if int(declared) > MAX_8609_BYTES:
            raise HTTPException(status_code=413, detail="Form 8609 PDF must be 5 MB or smaller.")
    length, chunks = 0, []
    async for chunk in request.stream():
        length += len(chunk)
        if length > MAX_8609_BYTES:
            raise HTTPException(status_code=413, detail="Form 8609 PDF must be 5 MB or smaller.")
        chunks.append(chunk)
    result = archive_8609(
        db, current_user=current_user, property_id=property_id,
        program_id=program_id, building_id=building_id,
        contents=b"".join(chunks), received_on=received_on,
        signed_copy_reviewed=signed_copy_reviewed,
    )
    response.headers.update(NO_STORE)
    return result


@router.get("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-documents/{document_id}/download")
def download_document(
    property_id: int, program_id: int, building_id: int, document_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    contents = download_8609(
        db, property_id=property_id, program_id=program_id,
        building_id=building_id, document_id=document_id, current_user=current_user,
    )
    return Response(
        content=contents, media_type="application/pdf",
        headers={
            **NO_STORE,
            "Content-Disposition": 'attachment; filename="form-8609-staff-scan.pdf"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-documents/rotate")
def rotate_document_encryption(
    property_id: int, program_id: int, building_id: int, response: Response,
    after_document_id: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=25),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Administrator-only, audited and paginated encryption-key rewrap."""
    result = rotate_building_scans(
        db, current_user=current_user, property_id=property_id,
        program_id=program_id, building_id=building_id,
        after_document_id=after_document_id, limit=limit,
    )
    response.headers.update(NO_STORE)
    return result
