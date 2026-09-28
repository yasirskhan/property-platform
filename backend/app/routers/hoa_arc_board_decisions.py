"""Record a board's ARC decision, with optional atomic member fee and follow-up.

A board member is authenticated by the existing customer login, active
same-property voting seat, and matching verified email. There is no separate
software legal-effect flag. Association staff still cannot make a decision
merely by creating a preliminary ARC review record.
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.models.contact import Contact
from app.models.gl_account import GLAccount
from app.models.hoa_arc_application import HOAARCReviewEvent
from app.models.hoa_arc_decision import HOAARCDecision, HOAARCMemberCharge
from app.models.hoa_association import HOAContactLink
from app.models.hoa_board import HOABoardSeat
from app.models.lease import Lease, LeaseStatus
from app.models.property import Unit
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderCategory, WorkOrderPriority, WorkOrderStatus
from app.routers.auth import get_current_user
from app.routers.hoa_arc_applications import _contact_link, _detail, _row
from app.routers.hoa_assessments import _scope
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_arc_application import HOAARCApplicationDetailOut, HOAARCDecisionIn
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA ARC board decisions"])


def _board_seat(db: Session, *, org: int, association_id: int, property_id: int,
                actor: User) -> HOABoardSeat:
    if not actor.is_verified:
        raise HTTPException(status_code=403, detail="Verified board login required.")
    # A preliminary seat alone cannot authorize another user to issue a
    # decision. The authenticated account and the scoped contact must match.
    seat = db.query(HOABoardSeat).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(Contact, Contact.id == HOAContactLink.contact_id).filter(
        HOABoardSeat.organization_id == org,
        HOABoardSeat.association_id == association_id,
        HOABoardSeat.property_id == property_id,
        HOABoardSeat.is_active.is_(True),
        HOABoardSeat.staff_voting_eligible.is_(True),
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
        func.lower(func.trim(Contact.email)) == actor.email.strip().lower(),
    ).order_by(HOABoardSeat.id).first()
    if seat is None:
        raise HTTPException(status_code=403, detail="Active matching board seat required.")
    return seat


def _member_user(db: Session, *, org: int, contact: Contact) -> User | None:
    if not contact.email:
        return None
    return db.query(User).filter(
        User.organization_id == org,
        User.is_active.is_(True),
        User.is_verified.is_(True),
        User.deleted_at.is_(None),
        func.lower(func.trim(User.email)) == contact.email.strip().lower(),
    ).first()


def _validate_fee(db: Session, *, actor: User, org: int, fee) -> tuple[GLAccount, GLAccount]:
    if any(
        not permission_allows_user(db, user=actor, menu_key=key)
        for key in ("ACCOUNTING.CHARGES", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.GL_ACCOUNTS")
    ):
        raise HTTPException(status_code=403, detail="Member fee accounting permission required.")
    if fee.receivable_gl_account_id == fee.income_gl_account_id:
        raise HTTPException(status_code=422, detail="Receivable and income GL must differ.")
    receivable, income = (
        db.query(GLAccount).filter(
            GLAccount.id == account_id,
            GLAccount.organization_id == org,
            GLAccount.account_type == account_type,
            GLAccount.is_active.is_(True),
            GLAccount.deleted_at.is_(None),
        ).first()
        for account_id, account_type in (
            (fee.receivable_gl_account_id, "ASSET"),
            (fee.income_gl_account_id, "INCOME"),
        )
    )
    if receivable is None or income is None:
        raise HTTPException(status_code=404, detail="Valid same-organization fee GL accounts required.")
    return receivable, income


def _follow_up_unit(db: Session, *, org: int, property_id: int,
                    unit_id: int, member: User | None) -> Unit:
    if member is None or member.role != UserRole.TENANT:
        raise HTTPException(status_code=409, detail="Follow-up work order requires a verified tenant applicant.")
    row = db.query(Unit).join(
        Lease, Lease.unit_id == Unit.id,
    ).filter(
        Unit.id == unit_id,
        Unit.property_id == property_id,
        Unit.is_active.is_(True),
        Unit.deleted_at.is_(None),
        Lease.tenant_id == member.id,
        Lease.status == LeaseStatus.ACTIVE,
    ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="Applicant has no active lease for the requested unit.")
    return row


@router.post(
    "/{association_id}/arc-applications/{application_id}/board-decision",
    response_model=HOAARCApplicationDetailOut,
)
def record_board_decision(
    association_id: int, application_id: int, payload: HOAARCDecisionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _row(
        db, org_id=org, association_id=association.id,
        property_id=payload.property_id, application_id=application_id,
    )
    # Lock the application before checking its terminal state. The decision
    # table's unique application key also rejects competing requests.
    row = db.query(type(row)).filter(type(row).id == row.id).with_for_update().one()
    if row.status not in {"READY_FOR_DECISION", "DECISION_PREPARED"}:
        raise HTTPException(status_code=409, detail="ARC application is not ready for a board decision.")
    if db.query(HOAARCDecision.id).filter(
        HOAARCDecision.organization_id == org,
        HOAARCDecision.application_id == row.id,
    ).first():
        raise HTTPException(status_code=409, detail="Board decision already recorded.")

    seat = _board_seat(
        db, org=org, association_id=association.id,
        property_id=payload.property_id, actor=current_user,
    )
    _link, contact = _contact_link(
        db, org_id=org, association_id=association.id,
        property_id=payload.property_id, link_id=row.applicant_contact_link_id,
    )
    member = _member_user(db, org=org, contact=contact)
    if (payload.fee is not None or payload.follow_up_unit_id is not None) and payload.decision != "APPROVED":
        raise HTTPException(status_code=422, detail="Only an approval can create a fee or follow-up.")
    if payload.follow_up_description and payload.follow_up_unit_id is None:
        raise HTTPException(status_code=422, detail="A follow-up unit is required.")
    if payload.fee is not None and member is None:
        raise HTTPException(status_code=409, detail="A verified applicant account is required for a member fee.")
    accounts = _validate_fee(db, actor=current_user, org=org, fee=payload.fee) if payload.fee else None
    unit = None
    if payload.follow_up_unit_id is not None:
        if not permission_allows_user(
            db, user=current_user, menu_key="MAINTENANCE.WORK_ORDERS",
        ):
            raise HTTPException(status_code=403, detail="Work order permission required.")
        unit = _follow_up_unit(
            db, org=org, property_id=payload.property_id,
            unit_id=payload.follow_up_unit_id, member=member,
        )

    now = datetime.utcnow()
    decision = HOAARCDecision(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, application_id=row.id,
        board_seat_id=seat.id, board_user_id=current_user.id,
        decision=payload.decision, decision_note=payload.decision_note,
        notification_status="PENDING" if member else "NO_VERIFIED_RECIPIENT",
        decided_at=now,
    )
    db.add(decision)
    try:
        db.flush()
        if accounts is not None and payload.fee is not None and member is not None:
            receivable, income = accounts
            txn = post_transaction(
                db, organization_id=org, transaction_date=now.date(),
                transaction_type="JOURNAL_ENTRY",
                memo="HOA ARC application fee",
                lines=[
                    PostingLine(
                        gl_account_id=receivable.id, property_id=payload.property_id,
                        debit=payload.fee.amount, credit=0,
                        description="ARC fee member receivable",
                    ),
                    PostingLine(
                        gl_account_id=income.id, property_id=payload.property_id,
                        debit=0, credit=payload.fee.amount,
                        description="ARC fee income",
                    ),
                ],
                created_by=current_user,
                reference_number=f"HOAARC{row.id}",
                source_type="hoa_arc_member_charge", source_id=row.id,
                commit=False, write_audit=False,
            )
            db.add(HOAARCMemberCharge(
                organization_id=org, association_id=association.id,
                property_id=payload.property_id, application_id=row.id,
                contact_link_id=row.applicant_contact_link_id,
                member_user_id=member.id, gl_transaction_id=txn.id,
                receivable_gl_account_id=receivable.id,
                income_gl_account_id=income.id,
                amount=payload.fee.amount, amount_paid=0, due_on=payload.fee.due_on,
                status="OPEN", created_at=now,
            ))
        if unit is not None and member is not None:
            wo = WorkOrder(
                unit_id=unit.id, tenant_id=member.id, property_id=payload.property_id,
                title=f"ARC approval follow-up #{row.id}",
                description=payload.follow_up_description or (
                    f"Follow up on board-approved ARC application #{row.id}."
                ),
                category=WorkOrderCategory.GENERAL,
                priority=WorkOrderPriority.LOW,
                status=WorkOrderStatus.SUBMITTED,
                permission_to_enter=False,
            )
            db.add(wo)
            db.flush()
            decision.work_order_id = wo.id
        row.status = payload.decision
        row.decision_preparation = None
        row.updated_by_id = current_user.id
        db.add(HOAARCReviewEvent(
            organization_id=org, application_id=row.id,
            event_type="BOARD_" + payload.decision, staff_note=None,
            created_by_id=current_user.id, created_at=now,
        ))
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_arc_decision", entity_id=decision.id,
            action="board_decision_recorded",
            new_value={
                "association_id": association.id,
                "property_id": row.property_id,
                "application_id": row.id, "decision": row.status,
                "fee_posted": payload.fee is not None,
                "work_order_created": unit is not None,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="ARC fee GL posting rejected: " + str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent ARC decision.") from exc
    except Exception:
        db.rollback()
        raise

    # The board's decision is durable before external email delivery. An
    # SMTP failure never rolls back a real board decision or repeats a fee.
    if member is not None:
        try:
            send_email(
                to=member.email, organization_id=org, db=db,
                subject="ARC application decision recorded",
                body=(
                    f"An ARC board decision for your application #{row.id} has "
                    f"been recorded: {payload.decision}. Contact the association "
                    "for the decision details and any associated charges."
                ),
            )
            decision.notification_status = "SENT"
        except Exception:
            decision.notification_status = "FAILED"
        db.commit()
    db.refresh(row)
    return _detail(db, row)


@router.get(
    "/{association_id}/arc-applications/{application_id}/member-fee",
    response_model=dict,
)
def get_member_fee(
    association_id: int, application_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(db, actor=current_user, association_id=association_id,
                        property_id=property_id, write=False)
    row = _row(db, org_id=org, association_id=assoc.id,
               property_id=property_id, application_id=application_id)
    if not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.CHARGES"):
        raise HTTPException(status_code=403, detail="Member ledger permission required.")
    charge = db.query(HOAARCMemberCharge).filter(
        HOAARCMemberCharge.organization_id == org,
        HOAARCMemberCharge.association_id == assoc.id,
        HOAARCMemberCharge.property_id == property_id,
        HOAARCMemberCharge.application_id == row.id,
    ).first()
    response.headers["Cache-Control"] = "no-store"
    if charge is None:
        return {"member_charge": None}
    return {"member_charge": {
        "id": charge.id, "amount": str(charge.amount),
        "amount_paid": str(charge.amount_paid), "due_on": charge.due_on.isoformat(),
        "status": charge.status, "gl_transaction_id": charge.gl_transaction_id,
    }}
