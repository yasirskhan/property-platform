"""No-temp-file PDF streaming for encrypted paper W-9 archives."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.tax_w9 import TaxW9DocumentOut
from app.services.tax_profiles import require_tax_admin
from app.services.tax_w9 import (
    MAX_W9_BYTES, archive_signed_w9, download_archived_w9, list_archived_w9,
)

router = APIRouter(prefix="/api/reporting/tax-w9", tags=["Restricted paper W-9 archive"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


@router.get("/{tax_profile_id}", response_model=list[TaxW9DocumentOut])
def list_w9_documents(
    tax_profile_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return list_archived_w9(db, current_user=current_user, tax_profile_id=tax_profile_id)


@router.post("/{tax_profile_id}", response_model=TaxW9DocumentOut, status_code=201)
async def upload_w9_document(
    tax_profile_id: int, request: Request, response: Response,
    received_on: date = Query(...),
    signed_original_confirmed: bool = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Never use UploadFile: multipart parsing can spool unencrypted PDFs to disk.
    require_tax_admin(db, current_user)
    if request.headers.get("content-type", "").split(";", 1)[0].lower().strip() != "application/pdf":
        raise HTTPException(status_code=415, detail="Send a PDF with application/pdf content type.")
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid content length.")
        if int(declared) > MAX_W9_BYTES:
            raise HTTPException(status_code=413, detail="W-9 PDF must be 5 MB or smaller.")
    chunks: list[bytes] = []
    length = 0
    async for chunk in request.stream():
        length += len(chunk)
        if length > MAX_W9_BYTES:
            raise HTTPException(status_code=413, detail="W-9 PDF must be 5 MB or smaller.")
        chunks.append(chunk)
    result = archive_signed_w9(
        db, current_user=current_user, tax_profile_id=tax_profile_id,
        contents=b"".join(chunks), received_on=received_on,
        signed_original_confirmed=signed_original_confirmed,
    )
    response.headers.update(NO_STORE)
    return result


@router.get("/{tax_profile_id}/{document_id}/download")
def download_w9_document(
    tax_profile_id: int, document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plain = download_archived_w9(
        db, current_user=current_user,
        tax_profile_id=tax_profile_id, document_id=document_id,
    )
    return Response(
        content=plain, media_type="application/pdf",
        headers={
            **NO_STORE,
            "Content-Disposition": 'attachment; filename="signed-w9.pdf"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Referrer-Policy": "no-referrer",
        },
    )
