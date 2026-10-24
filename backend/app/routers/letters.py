"""Org-scoped letter templates and verified, explicitly confirmed mail merge."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
import hmac
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.models.letter_template import LetterTemplate
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.letter import LetterPreviewOut, LetterSendIn, LetterSendOut, LetterTemplateIn, LetterTemplateOut
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.letters import require_letters_access, render_for_lease, scoped_letter, validate_letter

router = APIRouter(prefix="/api/reporting/letters", tags=["Letters"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _require_template_write(db: Session, user: User) -> int:
    org = require_letters_access(db, user)
    role = user.role.value if hasattr(user.role, "value") else str(user.role or "")
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can edit letter templates.")
    return org


def _require_delivery(db: Session, user: User) -> None:
    item = next((d for d in resolve_customer_features(db, user=user)
                 if d.key == "release.reporting.export"), None)
    if item is None or not item.allowed:
        raise HTTPException(status_code=404, detail="Letter delivery not available.")


def _out(row: LetterTemplate) -> LetterTemplateOut:
    return LetterTemplateOut(
        id=row.id, organization_id=row.organization_id,
        title=row.title, category=row.category, subject=row.subject,
        body=row.body, is_active=bool(row.is_active),
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("", response_model=list[LetterTemplateOut])
def list_letters(response: Response, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    org = require_letters_access(db, current_user)
    _no_store(response)
    rows = db.query(LetterTemplate).filter(
        LetterTemplate.organization_id == org,
        LetterTemplate.is_active.is_(True),
    ).order_by(LetterTemplate.id.asc()).all()
    return [_out(row) for row in rows]


@router.post("", response_model=LetterTemplateOut, status_code=201)
def create_letter(payload: LetterTemplateIn, response: Response,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    org = _require_template_write(db, current_user)
    validate_letter(payload.subject, payload.body)
    row = LetterTemplate(
        organization_id=org, title=payload.title, category=payload.category,
        subject=payload.subject, body=payload.body,
        created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(row)
    db.flush()
    append_audit_log(db, user_id=current_user.id, organization_id=org,
                     entity_type="letter_template", entity_id=row.id,
                     action="created", new_value={"title": row.title, "category": row.category})
    db.commit()
    db.refresh(row)
    _no_store(response)
    return _out(row)


@router.get("/{letter_id}", response_model=LetterTemplateOut)
def get_letter(letter_id: int, response: Response,
               db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    row = scoped_letter(db, user=current_user, letter_id=letter_id)
    _no_store(response)
    return _out(row)


@router.put("/{letter_id}", response_model=LetterTemplateOut)
def update_letter(letter_id: int, payload: LetterTemplateIn, response: Response,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    org = _require_template_write(db, current_user)
    row = scoped_letter(db, user=current_user, letter_id=letter_id)
    validate_letter(payload.subject, payload.body)
    old = {"title": row.title, "category": row.category}
    row.title, row.category, row.subject, row.body = (
        payload.title, payload.category, payload.subject, payload.body,
    )
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(db, user_id=current_user.id, organization_id=org,
                     entity_type="letter_template", entity_id=row.id, action="updated",
                     old_value=old, new_value={"title": row.title, "category": row.category})
    db.commit()
    db.refresh(row)
    _no_store(response)
    return _out(row)


@router.delete("/{letter_id}", status_code=204)
def delete_letter(letter_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    org = _require_template_write(db, current_user)
    row = scoped_letter(db, user=current_user, letter_id=letter_id)
    row.is_active = False
    append_audit_log(db, user_id=current_user.id, organization_id=org,
                     entity_type="letter_template", entity_id=row.id,
                     action="deactivated", new_value={"category": row.category})
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/{letter_id}/preview/{lease_id}", response_model=LetterPreviewOut)
def preview_letter(letter_id: int, lease_id: int, response: Response,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    row = scoped_letter(db, user=current_user, letter_id=letter_id)
    _require_delivery(db, current_user)
    result = render_for_lease(db, user=current_user, row=row, lease_id=lease_id)
    _no_store(response)
    return result


@router.post("/{letter_id}/email", response_model=LetterSendOut)
def send_letter(letter_id: int, payload: LetterSendIn, response: Response,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    row = scoped_letter(db, user=current_user, letter_id=letter_id)
    _require_delivery(db, current_user)
    if not payload.confirm_recipient or not payload.confirm_content_reviewed:
        raise HTTPException(status_code=422, detail="Confirm recipient and reviewed content.")
    if row.category == "THREE_DAY_NOTICE" and not payload.confirm_legal_review:
        raise HTTPException(status_code=422, detail="Legal notice review required.")
    result = render_for_lease(db, user=current_user, row=row, lease_id=payload.lease_id)
    if not hmac.compare_digest(payload.review_token, result.review_token):
        raise HTTPException(
            status_code=409,
            detail="Reviewed letter changed. Preview and confirm the current content again.",
        )
    # Destination is obtained exclusively from the current scoped lease; never
    # accept arbitrary supplied email, external recipient or unreviewed tokens.
    send_email(to=result.recipient_email, subject=result.subject, body=result.body,
               organization_id=row.organization_id, db=db)
    append_audit_log(db, user_id=current_user.id, organization_id=row.organization_id,
                     entity_type="letter_template", entity_id=row.id, action="letter_emailed",
                     new_value={"lease_id": result.lease_id, "tenant_id": result.tenant_id,
                                "category": row.category, "recipient_user_id": result.tenant_id})
    db.commit()
    _no_store(response)
    return LetterSendOut(sent=True, recipient_email=result.recipient_email)
