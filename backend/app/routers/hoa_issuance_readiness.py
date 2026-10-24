"""Fail-closed HOA assessment issuance and reversal prerequisites.

This is deliberately read-only. An HOA contact is not automatically a
legal debtor, staff-supplied governing evidence is not authenticated, and
a plan is not an issued receivable. Never call tenant Charge or GL posting.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.gl_account import GLAccount
from app.models.hoa_planned_occurrence import HOAPlannedOccurrence
from app.models.user import Organization, User, UserRole
from app.routers.auth import get_current_user
from app.routers.hoa_planned_occurrences import _scope, _rows, _payer
from app.schemas.hoa_issuance_readiness import HOAIssuanceReadinessOut
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA issuance prerequisites"])
REQUIRED_ACCOUNTING = ("ACCOUNTING.CHARGES", "ACCOUNTING.GL_ACCOUNTS")


@router.get(
    "/{association_id}/draft-assessments/{proposal_id}/planned-occurrences/{occurrence_id}/issuance-readiness",
    response_model=HOAIssuanceReadinessOut,
)
def issuance_readiness(
    association_id: int, proposal_id: int, occurrence_id: int,
    response: Response,
    property_id: int = Query(ge=1),
    candidate_income_gl_account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, proposal = _scope(
        db, current_user, association_id, property_id, proposal_id, write=False,
    )
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER) or any(
        not permission_allows_user(db, user=current_user, menu_key=key)
        for key in REQUIRED_ACCOUNTING
    ):
        raise HTTPException(status_code=403, detail="HOA accounting readiness requires administrator or owner.")

    row = _rows(db, org, assoc.id, property_id, proposal.id).filter(
        HOAPlannedOccurrence.id == occurrence_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Planning occurrence not found.")

    reasons = [
        "GOVERNING_AUTHORITY_UNVERIFIED",
        "ASSESSMENT_APPROVAL_UNVERIFIED",
        "LEGAL_PAYER_LIABILITY_UNVERIFIED",
        "APPROVED_GL_MAPPING_UNAVAILABLE",
    ]
    if row.status != "PLANNED":
        reasons.append("OCCURRENCE_VOIDED")
    # The payer row is only an unverified staff reference, but even that
    # reference must still exist and match the historical snapshot.
    try:
        payer = _payer(db, org, assoc.id, property_id, proposal.id)
    except HTTPException as exc:
        if exc.status_code not in (404, 409):
            raise
        payer = None
    if payer is None or payer.id != row.payer_draft_id:
        reasons.append("PAYER_REFERENCE_STALE")
    organization = db.query(Organization).filter(
        Organization.id == org,
    ).first()
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    unlocked = (
        organization.locked_through_date is None
        or row.proposed_on > organization.locked_through_date
    )
    if not unlocked:
        reasons.append("ACCOUNTING_PERIOD_LOCKED")

    candidate_valid = False
    if candidate_income_gl_account_id is not None:
        candidate_valid = db.query(GLAccount.id).filter(
            GLAccount.id == candidate_income_gl_account_id,
            GLAccount.organization_id == org,
            GLAccount.account_type == "INCOME",
            GLAccount.is_active.is_(True),
            GLAccount.deleted_at.is_(None),
        ).first() is not None
    if not candidate_valid:
        reasons.append("NO_VALID_INCOME_GL_CANDIDATE")

    response.headers["Cache-Control"] = "no-store"
    return HOAIssuanceReadinessOut(
        occurrence_id=row.id, property_id=property_id,
        proposed_on=row.proposed_on, proposed_amount=row.proposed_amount,
        status=row.status, accounting_period_unlocked=unlocked,
        candidate_income_account_valid=candidate_valid,
        missing_requirements=reasons,
    )
