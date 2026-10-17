"""HOA board-adopted assessments, actual member receivables and balanced GL.

An authenticated association board seat records its own decision. The
platform does not independently certify law. A separately authorized
accountant explicitly bills the verified same-scope member, with central
GL locking and immutable reversal. It never creates a tenant Charge.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.hoa_member_assessment import HOAAssessmentDecision, HOAMemberAssessmentCharge
from app.models.hoa_planned_occurrence import HOAPlannedOccurrence
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_applications import _contact_link
from app.routers.hoa_arc_board_decisions import (
    _board_scope, _decision_maker, _verified_member,
)
from app.routers.hoa_assessments import _record, _scope
from app.routers.hoa_planned_occurrences import _payer, _rows
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_member_assessment import (
    HOAAssessmentBoardDecisionIn, HOAAssessmentBoardDecisionOut,
    HOAChargeIssueIn, HOAChargeReverseIn, HOAMemberChargeOut,
)
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA adopted member assessments"])
_ACCOUNTING = ("ACCOUNTING.CHARGES", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.GL_ACCOUNTS")


def _accountant(db: Session, *, actor: User, assoc: int, prop: int):
    org, association = _scope(
        db, actor=actor, association_id=assoc, property_id=prop, write=True,
    )
    if any(not permission_allows_user(db, user=actor, menu_key=k) for k in _ACCOUNTING):
        raise HTTPException(status_code=403, detail="HOA member assessment accounting permission required.")
    return org, association


def _approved(db: Session, *, org: int, association_id: int,
              property_id: int, proposal_id: int, lock: bool = False):
    query = db.query(HOAAssessmentDecision).filter(
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == association_id,
        HOAAssessmentDecision.property_id == property_id,
        HOAAssessmentDecision.proposal_id == proposal_id,
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def _decision_out(row: HOAAssessmentDecision, db: Session):
    issued = db.query(HOAMemberAssessmentCharge.id).filter(
        HOAMemberAssessmentCharge.organization_id == row.organization_id,
        HOAMemberAssessmentCharge.decision_id == row.id,
    ).first() is not None
    return HOAAssessmentBoardDecisionOut(
        id=row.id, proposal_id=row.proposal_id, property_id=row.property_id,
        decision=row.decision, board_seat_id=row.board_seat_id,
        decision_maker_seat_id=row.decision_maker_seat_id,
        record_method=row.record_method, decided_on=row.decided_on,
        contact_link_id=row.contact_link_id, member_user_id=row.member_user_id,
        approved_amount=row.approved_amount,
        proposal_revision_at=row.proposal_revision_at, issued=issued,
    )


def _charge_out(row: HOAMemberAssessmentCharge, *, proposal_id: int):
    return HOAMemberChargeOut(
        id=row.id, proposal_id=proposal_id,
        occurrence_id=row.occurrence_id, property_id=row.property_id,
        member_user_id=row.member_user_id,
        amount=row.amount, amount_paid=row.amount_paid,
        due_on=row.due_on, status=row.status,
        gl_transaction_id=row.gl_transaction_id,
        reversal_transaction_id=row.reversal_transaction_id,
        issued_at=row.issued_at,
    )


@router.post("/{association_id}/draft-assessments/{proposal_id}/board-decision",
             response_model=HOAAssessmentBoardDecisionOut, status_code=201)
def record_assessment_decision(
    association_id: int, proposal_id: int, payload: HOAAssessmentBoardDecisionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, recorder_seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    proposal = db.query(HOAAssessmentProposal).filter(
        HOAAssessmentProposal.id == proposal_id,
        HOAAssessmentProposal.organization_id == org,
        HOAAssessmentProposal.association_id == association.id,
        HOAAssessmentProposal.property_id == payload.property_id,
        HOAAssessmentProposal.is_active.is_(True),
    ).with_for_update().first()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Active assessment proposal not found.")
    if _approved(db, org=org, association_id=association.id,
                 property_id=payload.property_id, proposal_id=proposal.id) is not None:
        raise HTTPException(status_code=409, detail="Assessment already has a final board decision.")
    member = None
    link = None
    if payload.decision == "APPROVED":
        payer = _payer(db, org, association.id, payload.property_id, proposal.id)
        if payer.contact_link_id != payload.contact_link_id:
            raise HTTPException(status_code=409, detail="Board-approved member must match the current suggested payer reference.")
        link, contact = _contact_link(
            db, org_id=org, association_id=association.id,
            property_id=payload.property_id, link_id=payload.contact_link_id,
        )
        member = _verified_member(db, org=org, contact=contact)
        if member is None or member.id != payload.member_user_id:
            raise HTTPException(status_code=409, detail="Responsible member account must match verified association contact.")
    decision_day = date.today()
    maker = recorder_seat
    supporting = None
    method = "DIRECT"
    if payload.offline_meeting_on is not None:
        if not recorder_seat.can_record_offline:
            raise HTTPException(status_code=403, detail="Offline decision requires designated board recorder.")
        maker = _decision_maker(
            db, org=org, association_id=association.id,
            property_id=payload.property_id, seat_id=payload.decision_maker_seat_id,
        )
        supporting = db.query(EntityAttachment).filter(
            EntityAttachment.id == payload.supporting_attachment_id,
            EntityAttachment.organization_id == org,
            EntityAttachment.entity_type == "properties",
            EntityAttachment.entity_id == payload.property_id,
            EntityAttachment.is_active.is_(True),
            EntityAttachment.share_with_owners.is_(False),
            EntityAttachment.share_with_tenants.is_(False),
        ).first()
        if supporting is None:
            raise HTTPException(status_code=404, detail="Private board meeting record not found.")
        method = "OFFLINE"
        decision_day = payload.offline_meeting_on
    if decision_day > date.today():
        raise HTTPException(status_code=422, detail="Cannot record a future board decision.")
    row = HOAAssessmentDecision(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, proposal_id=proposal.id,
        board_seat_id=recorder_seat.id, board_user_id=current_user.id,
        decision=payload.decision, decision_note=payload.decision_note,
        decided_on=decision_day, decided_at=datetime.utcnow(),
        decision_maker_seat_id=maker.id, record_method=method,
        supporting_attachment_id=supporting.id if supporting else None,
        contact_link_id=link.id if link else None,
        member_user_id=member.id if member else None,
        approved_amount=proposal.proposed_amount if member else None,
        proposal_revision_at=proposal.updated_at,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_assessment_decision", entity_id=row.id,
            action="board_assessment_decision_recorded",
            new_value={
                "association_id": association.id, "property_id": payload.property_id,
                "proposal_id": proposal.id, "decision": row.decision,
                "board_seat_id": recorder_seat.id,
                "decision_maker_seat_id": maker.id, "record_method": method,
                "member_user_id": row.member_user_id,
                "approved_amount": str(row.approved_amount) if member else None,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent assessment decision.") from exc
    db.refresh(row)
    return _decision_out(row, db)


@router.get("/{association_id}/draft-assessments/{proposal_id}/board-decision",
            response_model=HOAAssessmentBoardDecisionOut | None)
def get_assessment_decision(
    association_id: int, proposal_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _accountant(
        db, actor=current_user, assoc=association_id, prop=property_id,
    )
    _record(db, org_id=org, association_id=association.id,
            property_id=property_id, proposal_id=proposal_id)
    row = _approved(db, org=org, association_id=association.id,
                    property_id=property_id, proposal_id=proposal_id)
    response.headers["Cache-Control"] = "no-store"
    return _decision_out(row, db) if row else None


def _require_approval(db: Session, *, org: int, association_id: int,
                      property_id: int, proposal_id: int):
    proposal = _record(
        db, org_id=org, association_id=association_id,
        property_id=property_id, proposal_id=proposal_id,
    )
    decision = _approved(
        db, org=org, association_id=association_id,
        property_id=property_id, proposal_id=proposal_id, lock=True,
    )
    if decision is None or decision.decision != "APPROVED":
        raise HTTPException(status_code=409, detail="Authorized board assessment approval required.")
    if decision.proposal_revision_at != proposal.updated_at or decision.approved_amount != proposal.proposed_amount:
        raise HTTPException(status_code=409, detail="Assessment proposal has changed since board decision.")
    payer = _payer(db, org, association_id, property_id, proposal_id)
    if payer.contact_link_id != decision.contact_link_id:
        raise HTTPException(status_code=409, detail="Current payer reference differs from approved member.")
    link, contact = _contact_link(
        db, org_id=org, association_id=association_id,
        property_id=property_id, link_id=decision.contact_link_id,
    )
    member = _verified_member(db, org=org, contact=contact)
    if member is None or member.id != decision.member_user_id:
        raise HTTPException(status_code=409, detail="Approved member identity no longer matches current verified contact.")
    return proposal, decision, payer, member


def _accounts(db: Session, *, org: int, receivable_id: int, income_id: int):
    if receivable_id == income_id:
        raise HTTPException(status_code=422, detail="Receivable and income GL accounts must differ.")
    accounts = []
    for ident, kind in ((receivable_id, "ASSET"), (income_id, "INCOME")):
        account = db.query(GLAccount).filter(
            GLAccount.id == ident, GLAccount.organization_id == org,
            GLAccount.account_type == kind,
            GLAccount.is_active.is_(True), GLAccount.deleted_at.is_(None),
        ).first()
        if account is None:
            raise HTTPException(status_code=404, detail="Active scoped assessment GL accounts required.")
        accounts.append(account)
    return accounts


@router.post("/{association_id}/draft-assessments/{proposal_id}/planned-occurrences/{occurrence_id}/issue",
             response_model=HOAMemberChargeOut, status_code=201)
def issue_assessment(
    association_id: int, proposal_id: int, occurrence_id: int,
    payload: HOAChargeIssueIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    # Serialize assessment issuance with planning edits/voids on PostgreSQL.
    occurrence = _rows(db, org, association.id, payload.property_id, proposal_id).filter(
        HOAPlannedOccurrence.id == occurrence_id,
    ).with_for_update().first()
    if occurrence is None:
        raise HTTPException(status_code=404, detail="Scoped planned assessment not found.")
    existing = db.query(HOAMemberAssessmentCharge).filter(
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == association.id,
        HOAMemberAssessmentCharge.property_id == payload.property_id,
        HOAMemberAssessmentCharge.occurrence_id == occurrence.id,
    ).first()
    if existing is not None:
        if (existing.member_user_id != payload.member_user_id
                or existing.due_on != payload.due_on
                or existing.receivable_gl_account_id != payload.receivable_gl_account_id
                or existing.income_gl_account_id != payload.income_gl_account_id):
            raise HTTPException(status_code=409, detail="Assessment already issued with different terms.")
        return _charge_out(existing, proposal_id=proposal_id)
    if occurrence.status != "PLANNED":
        raise HTTPException(status_code=409, detail="Voided assessment period cannot be issued.")
    proposal, decision, payer, member = _require_approval(
        db, org=org, association_id=association.id,
        property_id=payload.property_id, proposal_id=proposal_id,
    )
    if (occurrence.payer_draft_id != payer.id or
            occurrence.proposal_revision_at != decision.proposal_revision_at or
            occurrence.proposed_amount != decision.approved_amount):
        raise HTTPException(status_code=409, detail="Planned occurrence differs from board-approved amount or payer.")
    if member.id != payload.member_user_id:
        raise HTTPException(status_code=409, detail="Responsible member does not match approved account.")
    if payload.due_on < occurrence.proposed_on or payload.due_on < date.today():
        raise HTTPException(status_code=422, detail="Assessment due date must not precede the period or issuance.")
    receivable, income = _accounts(
        db, org=org, receivable_id=payload.receivable_gl_account_id,
        income_id=payload.income_gl_account_id,
    )
    try:
        txn = post_transaction(
            db, organization_id=org, transaction_date=date.today(),
            transaction_type="JOURNAL_ENTRY", memo="HOA approved member assessment",
            lines=[
                PostingLine(gl_account_id=receivable.id, property_id=payload.property_id,
                            debit=decision.approved_amount, credit=Decimal("0")),
                PostingLine(gl_account_id=income.id, property_id=payload.property_id,
                            debit=Decimal("0"), credit=decision.approved_amount),
            ], created_by=current_user,
            reference_number=f"HOA{occurrence.id}",
            source_type="hoa_member_assessment_charge", source_id=occurrence.id,
            commit=False, write_audit=False,
        )
        charge = HOAMemberAssessmentCharge(
            organization_id=org, association_id=association.id,
            property_id=payload.property_id, decision_id=decision.id,
            occurrence_id=occurrence.id, member_user_id=member.id,
            contact_link_id=decision.contact_link_id,
            receivable_gl_account_id=receivable.id, income_gl_account_id=income.id,
            gl_transaction_id=txn.id, amount=decision.approved_amount,
            amount_paid=Decimal("0"), due_on=payload.due_on,
            status="OPEN", issued_at=datetime.utcnow(),
        )
        db.add(charge)
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_member_assessment_charge", entity_id=charge.id,
            action="member_assessment_issued",
            new_value={
                "association_id": association.id, "property_id": payload.property_id,
                "proposal_id": proposal_id, "occurrence_id": occurrence.id,
                "member_user_id": member.id, "amount": str(charge.amount),
                "due_on": charge.due_on.isoformat(),
                "gl_transaction_id": txn.id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="HOA assessment GL posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate assessment issuance.") from exc
    db.refresh(charge)
    return _charge_out(charge, proposal_id=proposal_id)


@router.get("/{association_id}/draft-assessments/{proposal_id}/member-ledger",
            response_model=list[HOAMemberChargeOut])
def list_member_assessments(
    association_id: int, proposal_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _accountant(db, actor=current_user, assoc=association_id, prop=property_id)
    _record(db, org_id=org, association_id=association.id,
            property_id=property_id, proposal_id=proposal_id)
    items = db.query(HOAMemberAssessmentCharge).join(
        HOAAssessmentDecision, HOAAssessmentDecision.id == HOAMemberAssessmentCharge.decision_id,
    ).filter(
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == association.id,
        HOAMemberAssessmentCharge.property_id == property_id,
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == association.id,
        HOAAssessmentDecision.property_id == property_id,
        HOAAssessmentDecision.proposal_id == proposal_id,
    ).order_by(HOAMemberAssessmentCharge.id).limit(501).all()
    if len(items) > 500:
        raise HTTPException(status_code=422, detail="Too many member assessment entries.")
    response.headers["Cache-Control"] = "no-store"
    return [_charge_out(row, proposal_id=proposal_id) for row in items]


@router.post("/{association_id}/draft-assessments/{proposal_id}/member-ledger/{charge_id}/reverse",
             response_model=HOAMemberChargeOut)
def reverse_assessment(
    association_id: int, proposal_id: int, charge_id: int,
    payload: HOAChargeReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    _record(db, org_id=org, association_id=association.id,
            property_id=payload.property_id, proposal_id=proposal_id)
    row = db.query(HOAMemberAssessmentCharge).join(
        HOAAssessmentDecision, HOAAssessmentDecision.id == HOAMemberAssessmentCharge.decision_id,
    ).filter(
        HOAMemberAssessmentCharge.id == charge_id,
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == association.id,
        HOAMemberAssessmentCharge.property_id == payload.property_id,
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.proposal_id == proposal_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Scoped member assessment not found.")
    if row.status != "OPEN" or row.amount_paid != Decimal("0") or row.reversal_transaction_id is not None:
        raise HTTPException(status_code=409, detail="Paid or already reversed member assessment cannot be reversed.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == row.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if original is None or original.source_type != "hoa_member_assessment_charge" or original.source_id != row.occurrence_id:
        raise HTTPException(status_code=409, detail="Original assessment GL source invalid.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Reversal must not precede original or be future-dated.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == org, GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2:
        raise HTTPException(status_code=409, detail="Unexpected original assessment GL shape.")
    try:
        reverse = post_transaction(
            db, organization_id=org, transaction_date=payload.reversal_on,
            transaction_type="REVERSAL", memo="HOA member assessment reversal",
            lines=[
                PostingLine(gl_account_id=e.gl_account_id, property_id=e.property_id,
                            unit_id=e.unit_id, owner_id=e.owner_id,
                            debit=e.credit, credit=e.debit) for e in entries
            ], created_by=current_user,
            source_type="hoa_member_assessment_charge", source_id=row.occurrence_id,
            reversal_of_id=original.id, commit=False, write_audit=False,
        )
        original.is_reversed = True
        row.status = "REVERSED"
        row.reversal_transaction_id = reverse.id
        row.reversal_reason = payload.reason.strip()
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_member_assessment_charge", entity_id=row.id,
            action="member_assessment_reversed",
            new_value={
                "association_id": association.id, "property_id": payload.property_id,
                "proposal_id": proposal_id, "occurrence_id": row.occurrence_id,
                "reversal_gl_transaction_id": reverse.id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Assessment reversal GL posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent assessment reversal.") from exc
    db.refresh(row)
    return _charge_out(row, proposal_id=proposal_id)
