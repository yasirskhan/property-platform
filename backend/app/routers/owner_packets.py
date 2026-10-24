"""Review and send existing immutable statement snapshot as an owner packet."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.owner_packet import OwnerPacketPreviewOut, OwnerPacketSendIn, OwnerPacketSendOut
from app.services.audit import append_audit_log
from app.services.owner_packets import build_packet

router = APIRouter(prefix="/api/accounting/owner-packets", tags=["Owner Packets"])


@router.get("/{statement_id}/preview", response_model=OwnerPacketPreviewOut)
def preview_owner_packet(
    statement_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    packet = build_packet(db, actor=current_user, statement_id=statement_id)
    response.headers["Cache-Control"] = "no-store"
    return packet.preview


@router.post("/{statement_id}/email", response_model=OwnerPacketSendOut)
def email_owner_packet(
    statement_id: int, payload: OwnerPacketSendIn, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    packet = build_packet(db, actor=current_user, statement_id=statement_id)
    if not packet.preview.email_enabled:
        raise HTTPException(status_code=403, detail="Owner packet email is disabled in settings.")
    if not payload.confirm_recipient or not payload.confirm_snapshot_reviewed:
        raise HTTPException(status_code=422, detail="Review and confirm the owner and packet.")
    if not hmac.compare_digest(payload.review_token, packet.preview.review_token):
        raise HTTPException(status_code=409, detail="Owner packet changed. Preview it again.")
    # Recipient is resolved from current, scoped owner; never accept client email.
    send_email(
        to=packet.preview.recipient_email, subject=packet.subject, body=packet.body,
        organization_id=current_user.organization_id, db=db,
        attachments=list(packet.files),
    )
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="owner_packet", entity_id=statement_id,
        action="emailed", new_value={
            "statement_id": statement_id, "owner_id": packet.preview.owner_id,
            "filenames": packet.preview.attachment_filenames,
            "attachment_format": "CSV",
        },
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return OwnerPacketSendOut(
        sent=True, recipient_email=packet.preview.recipient_email,
        filenames=packet.preview.attachment_filenames,
    )
