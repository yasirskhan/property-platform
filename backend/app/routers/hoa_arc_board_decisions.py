"""Authenticated HOA board ARC decisions, atomic side effects and a retryable outbox.

An authorized association board member records the board's decision directly.
No software-level legal_effect flag or governing-document upload gate exists.
A decision's optional financial effects require an explicitly verified member
and same-organization GL accounts; no tenant charge is inferred from a contact.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.models.contact import Contact
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_arc_application import HOAARCApplication, HOAARCReviewEvent
from app.models.hoa_arc_decision import (
    HOAARCDecision, HOAARCFollowUp, HOAARCMemberCharge, HOAARCNotification,
)
from app.models.hoa_association import HOAAssociation, HOAContactLink, HOAPropertyMembership
from app.models.hoa_board import HOABoardSeat
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder, WorkOrderCategory, WorkOrderPriority, WorkOrderStatus
from app.routers.auth import get_current_user
from app.routers.hoa_arc_applications import _contact_link, _detail, _row
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_arc_application import HOAARCApplicationDetailOut, HOAARCDecisionIn
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.gl_posting import PostingError, post_transaction
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA ARC board decisions"])
HOA_GATES = ("release.properties.compliance", "release.properties.hoa")


class HOAARCReversalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    reversal_on: date
    reason: str = Field(min_length=1, max_length=500)


def _board_scope(
    db: Session, *, actor: User, association_id: int, property_id: int,
) -> tuple[int, HOAAssociation, HOABoardSeat]:
    if (
        actor.organization_id is None or not actor.is_active
        or actor.deleted_at is not None or not actor.is_verified
    ):
        raise HTTPException(status_code=403, detail="Verified active board login required.")
    org = db.query(Organization).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True),
        Organization.deleted_at.is_(None),
    ).first()
    if org is None:
        raise HTTPException(status_code=403, detail="Organization inactive.")
    # Board delegation substitutes for PROPERTIES.ALL. Never bypass the
    # existing paid feature, live release gate or organization enablement.
    decisions = {item.key: item for item in resolve_customer_features(db, user=actor)}
    if any(
        (value := decisions.get(key)) is None
        or not (value.release_allowed and value.entitlement_allowed and value.org_config_allowed)
        for key in HOA_GATES
    ):
        raise HTTPException(status_code=404, detail="HOA module unavailable.")
    association = db.query(HOAAssociation).filter(
        HOAAssociation.id == association_id,
        HOAAssociation.organization_id == org.id,
        HOAAssociation.is_active.is_(True),
    ).first()
    property_found = db.query(Property.id).join(
        HOAPropertyMembership, HOAPropertyMembership.property_id == Property.id,
    ).filter(
        Property.id == property_id,
        Property.organization_id == org.id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
        HOAPropertyMembership.organization_id == org.id,
        HOAPropertyMembership.association_id == association_id,
    ).first()
    if association is None or property_found is None:
        raise HTTPException(status_code=404, detail="Association property not found.")
    seat = db.query(HOABoardSeat).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(Contact, Contact.id == HOAContactLink.contact_id).filter(
        HOABoardSeat.organization_id == org.id,
        HOABoardSeat.association_id == association_id,
        HOABoardSeat.property_id == property_id,
        HOABoardSeat.is_active.is_(True),
        HOABoardSeat.decision_authorized.is_(True),
        HOABoardSeat.staff_voting_eligible.is_(True),
        HOABoardSeat.authorized_user_id == actor.id,
        HOAContactLink.organization_id == org.id,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org.id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
        func.lower(func.trim(Contact.email)) == actor.email.strip().lower(),
    ).order_by(HOABoardSeat.id).first()
    if seat is None:
        raise HTTPException(status_code=403, detail="Active authorized board seat required.")
    return org.id, association, seat


def _decision_maker(
    db: Session, *, org: int, association_id: int, property_id: int,
    seat_id: int,
) -> HOABoardSeat:
    seat = db.query(HOABoardSeat).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(Contact, Contact.id == HOAContactLink.contact_id).join(
        User, User.id == HOABoardSeat.authorized_user_id,
    ).filter(
        HOABoardSeat.id == seat_id,
        HOABoardSeat.organization_id == org,
        HOABoardSeat.association_id == association_id,
        HOABoardSeat.property_id == property_id,
        HOABoardSeat.is_active.is_(True),
        HOABoardSeat.decision_authorized.is_(True),
        HOABoardSeat.staff_voting_eligible.is_(True),
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
        User.organization_id == org, User.is_active.is_(True),
        User.is_verified.is_(True), User.deleted_at.is_(None),
        func.lower(func.trim(User.email)) == func.lower(func.trim(Contact.email)),
    ).first()
    if seat is None:
        raise HTTPException(status_code=409, detail="Offline decision maker has no active authenticated seat.")
    return seat


def _verified_member(db: Session, *, org: int, contact: Contact) -> User | None:
    if not contact.email:
        return None
    return db.query(User).filter(
        User.organization_id == org,
        User.is_active.is_(True),
        User.is_verified.is_(True),
        User.deleted_at.is_(None),
        func.lower(func.trim(User.email)) == contact.email.strip().lower(),
    ).first()


def _fee_accounts(db: Session, *, org: int, actor: User, fee):
    if any(
        not permission_allows_user(db, user=actor, menu_key=key)
        for key in ("ACCOUNTING.CHARGES", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.GL_ACCOUNTS")
    ):
        raise HTTPException(status_code=403, detail="ARC fee requires accounting permissions.")
    if fee.receivable_gl_account_id == fee.income_gl_account_id:
        raise HTTPException(status_code=422, detail="ARC receivable and income accounts must differ.")
    accounts = []
    for account_id, account_type in (
        (fee.receivable_gl_account_id, "ASSET"),
        (fee.income_gl_account_id, "INCOME"),
    ):
        account = db.query(GLAccount).filter(
            GLAccount.id == account_id, GLAccount.organization_id == org,
            GLAccount.account_type == account_type,
            GLAccount.is_active.is_(True), GLAccount.deleted_at.is_(None),
        ).first()
        if account is None:
            raise HTTPException(status_code=404, detail="Valid scoped fee GL account required.")
        accounts.append(account)
    return accounts


def _send_notification(db: Session, *, notification_id: int, actor: User) -> str:
    """Claim before SMTP, then durably store SENT/FAILED, never re-create money.

    A stale SENDING claim can be retried after ten minutes. SMTP itself
    cannot promise exactly-once delivery; the outbox is at-least-once.
    """
    row = db.query(HOAARCNotification).filter(
        HOAARCNotification.id == notification_id,
        HOAARCNotification.organization_id == actor.organization_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if row.status == "SENT":
        return "SENT"
    if row.status == "SENDING" and row.last_attempt_at and (
        datetime.utcnow() - row.last_attempt_at < timedelta(minutes=10)
    ):
        raise HTTPException(status_code=409, detail="Notification delivery is in progress.")
    if row.attempt_count >= 20:
        raise HTTPException(status_code=409, detail="Notification retry limit reached.")
    member = db.query(User).filter(
        User.id == row.recipient_user_id,
        User.organization_id == row.organization_id,
        User.is_active.is_(True), User.is_verified.is_(True),
        User.deleted_at.is_(None),
        func.lower(func.trim(User.email)) == row.recipient_email.lower(),
    ).first()
    if member is None:
        raise HTTPException(status_code=409, detail="Recipient is no longer verified.")
    decision = db.query(HOAARCDecision).filter(
        HOAARCDecision.id == row.decision_id,
        HOAARCDecision.organization_id == row.organization_id,
        HOAARCDecision.association_id == row.association_id,
        HOAARCDecision.property_id == row.property_id,
    ).first()
    if decision is None:
        raise HTTPException(status_code=404, detail="Board decision not found.")
    row.status = "SENDING"
    decision.notification_status = "SENDING"
    row.attempt_count += 1
    row.last_attempt_at = datetime.utcnow()
    db.commit()
    try:
        send_email(
            to=row.recipient_email,
            subject="Your ARC application decision",
            body=(
                f"The board has recorded {decision.decision} for your ARC "
                f"application #{decision.application_id}. Please contact your "
                "association for the decision record and any fee details."
            ),
            organization_id=row.organization_id, db=db,
        )
    except Exception:
        row.status = "FAILED"
    else:
        row.status = "SENT"
        row.sent_at = datetime.utcnow()
    decision.notification_status = row.status
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_arc_notification", entity_id=row.id,
        action=("notification_sent" if row.status == "SENT" else "notification_failed"),
        new_value={"decision_id": row.decision_id, "attempt_count": row.attempt_count},
    )
    db.commit()
    return row.status


@router.post(
    "/{association_id}/arc-applications/{application_id}/board-decision",
    response_model=HOAARCApplicationDetailOut,
)
def record_board_decision(
    association_id: int, application_id: int, payload: HOAARCDecisionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, recorder_seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    row = db.query(HOAARCApplication).filter(
        HOAARCApplication.id == application_id,
        HOAARCApplication.organization_id == org,
        HOAARCApplication.association_id == association.id,
        HOAARCApplication.property_id == payload.property_id,
        HOAARCApplication.is_active.is_(True),
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="ARC application not found.")
    if row.status not in {"READY_FOR_DECISION", "DECISION_PREPARED"}:
        raise HTTPException(status_code=409, detail="Application already decided or not ready.")
    if db.query(HOAARCDecision.id).filter(
        HOAARCDecision.organization_id == org,
        HOAARCDecision.application_id == row.id,
    ).first():
        raise HTTPException(status_code=409, detail="Board decision already recorded.")

    link, contact = _contact_link(
        db, org_id=org, association_id=association.id,
        property_id=payload.property_id, link_id=row.applicant_contact_link_id,
    )
    decision_day = date.today()
    maker_seat = recorder_seat
    supporting = None
    record_method = "DIRECT"
    if payload.offline_meeting_on is not None:
        if not recorder_seat.can_record_offline:
            raise HTTPException(status_code=403, detail="Offline recording requires a designated officer.")
        maker_seat = _decision_maker(
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
            raise HTTPException(status_code=404, detail="Private offline board record not found.")
        record_method = "OFFLINE"
        decision_day = payload.offline_meeting_on
    if not row.submitted_on <= decision_day <= date.today():
        raise HTTPException(status_code=422, detail="Decision date outside application lifetime.")

    member = _verified_member(db, org=org, contact=contact)
    if payload.decision != "APPROVED" and (payload.fee is not None or payload.follow_up_kind is not None):
        raise HTTPException(status_code=422, detail="Only approval may create ARC consequences.")
    fee_accounts = None
    if payload.fee is not None:
        if member is None or member.id != payload.fee.member_user_id:
            raise HTTPException(status_code=409, detail="Responsible member login must match verified applicant.")
        fee_accounts = _fee_accounts(db, org=org, actor=current_user, fee=payload.fee)
    unit = None
    if payload.follow_up_unit_id is not None:
        unit = db.query(Unit).filter(
            Unit.id == payload.follow_up_unit_id,
            Unit.property_id == payload.property_id,
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        ).first()
        if unit is None:
            raise HTTPException(status_code=404, detail="HOA work-order unit not found.")
    existing_workorder_member = None
    if unit is not None and member is not None and member.role == UserRole.TENANT:
        active_lease = db.query(Lease.id).filter(
            Lease.unit_id == unit.id,
            Lease.tenant_id == member.id,
            Lease.status == LeaseStatus.ACTIVE,
        ).first()
        if active_lease is not None:
            existing_workorder_member = member

    now = datetime.utcnow()
    decision = HOAARCDecision(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, application_id=row.id,
        board_seat_id=recorder_seat.id, board_user_id=current_user.id,
        decision_maker_seat_id=maker_seat.id,
        decision=payload.decision, decision_note=payload.decision_note,
        decided_on=decision_day, record_method=record_method,
        supporting_attachment_id=supporting.id if supporting else None,
        decided_at=now,
        notification_status="PENDING" if member is not None else "NO_VERIFIED_RECIPIENT",
    )
    db.add(decision)
    try:
        db.flush()
        if payload.fee is not None and fee_accounts is not None and member is not None:
            receivable, income = fee_accounts
            txn = post_transaction(
                db, organization_id=org, transaction_date=now.date(),
                transaction_type="JOURNAL_ENTRY", memo="HOA ARC fee",
                lines=[
                    PostingLine(
                        gl_account_id=receivable.id, property_id=payload.property_id,
                        debit=payload.fee.amount, credit=Decimal("0"),
                    ),
                    PostingLine(
                        gl_account_id=income.id, property_id=payload.property_id,
                        debit=Decimal("0"), credit=payload.fee.amount,
                    ),
                ],
                created_by=current_user, reference_number=f"ARC{row.id}",
                source_type="hoa_arc_member_charge", source_id=decision.id,
                commit=False, write_audit=False,
            )
            db.add(HOAARCMemberCharge(
                organization_id=org, association_id=association.id,
                property_id=payload.property_id, application_id=row.id,
                contact_link_id=link.id, member_user_id=member.id,
                gl_transaction_id=txn.id,
                receivable_gl_account_id=receivable.id,
                income_gl_account_id=income.id,
                amount=payload.fee.amount, amount_paid=Decimal("0"),
                due_on=payload.fee.due_on, status="OPEN", created_at=now,
            ))
        if payload.follow_up_kind is not None:
            linked_work_order_id = None
            if unit is not None and existing_workorder_member is not None and (
                payload.follow_up_kind == "WORK_ORDER"
            ):
                work_order = WorkOrder(
                    unit_id=unit.id, tenant_id=existing_workorder_member.id,
                    property_id=payload.property_id,
                    title=f"ARC board follow-up #{row.id}",
                    description=payload.follow_up_description,
                    category=WorkOrderCategory.GENERAL,
                    priority=WorkOrderPriority.LOW,
                    status=WorkOrderStatus.SUBMITTED,
                    permission_to_enter=False,
                )
                db.add(work_order)
                db.flush()
                linked_work_order_id = work_order.id
                decision.work_order_id = linked_work_order_id
            db.add(HOAARCFollowUp(
                organization_id=org, association_id=association.id,
                property_id=payload.property_id, decision_id=decision.id,
                kind=payload.follow_up_kind,
                description=payload.follow_up_description,
                existing_work_order_id=linked_work_order_id,
                status="OPEN", created_at=now,
            ))
        if member is not None:
            db.add(HOAARCNotification(
                organization_id=org, association_id=association.id,
                property_id=payload.property_id, decision_id=decision.id,
                recipient_user_id=member.id, recipient_email=member.email,
                status="PENDING", attempt_count=0, created_at=now,
            ))
        row.status = payload.decision
        row.decision_preparation = None
        row.updated_by_id = current_user.id
        db.add(HOAARCReviewEvent(
            organization_id=org, application_id=row.id,
            event_type="BOARD_" + payload.decision,
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
                "recorder_seat_id": recorder_seat.id,
                "decision_maker_seat_id": maker_seat.id,
                "decided_on": decision_day.isoformat(),
                "record_method": record_method,
                "supporting_attachment_id": decision.supporting_attachment_id,
                "fee_posted": payload.fee is not None,
                "follow_up": payload.follow_up_kind,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="ARC fee GL posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate ARC decision.") from exc
    except Exception:
        db.rollback()
        raise

    # Delivery is a separate operation. Failure never reverses the board's
    # recorded decision or double-posts the member fee on retry.
    notice = db.query(HOAARCNotification).filter(
        HOAARCNotification.organization_id == org,
        HOAARCNotification.decision_id == decision.id,
    ).first()
    if notice is not None:
        try:
            _send_notification(db, notification_id=notice.id, actor=current_user)
        except Exception:
            # A crash/interrupted delivery remains claimed or pending and can
            # be explicitly retried without re-running decision side effects.
            db.rollback()
    db.refresh(row)
    return _detail(db, row)


@router.post(
    "/{association_id}/arc-applications/{application_id}/notification/retry",
    response_model=HOAARCApplicationDetailOut,
)
def retry_arc_notification(
    association_id: int, application_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, _ = _board_scope(
        db, actor=current_user, association_id=association_id, property_id=property_id,
    )
    row = _row(
        db, org_id=org, association_id=association.id,
        property_id=property_id, application_id=application_id,
    )
    decision = db.query(HOAARCDecision).filter(
        HOAARCDecision.organization_id == org,
        HOAARCDecision.association_id == association.id,
        HOAARCDecision.property_id == property_id,
        HOAARCDecision.application_id == row.id,
    ).first()
    if decision is None:
        raise HTTPException(status_code=404, detail="Board decision not found.")
    notification = db.query(HOAARCNotification).filter(
        HOAARCNotification.organization_id == org,
        HOAARCNotification.decision_id == decision.id,
    ).first()
    if notification is None:
        _, contact = _contact_link(
            db, org_id=org, association_id=association.id,
            property_id=property_id, link_id=row.applicant_contact_link_id,
        )
        member = _verified_member(db, org=org, contact=contact)
        if member is None:
            raise HTTPException(status_code=409, detail="No verified recipient for ARC notice.")
        notification = HOAARCNotification(
            organization_id=org, association_id=association.id,
            property_id=property_id, decision_id=decision.id,
            recipient_user_id=member.id, recipient_email=member.email,
            status="PENDING", attempt_count=0,
        )
        db.add(notification)
        try:
            db.flush()
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Notification already queued.") from exc
    _send_notification(db, notification_id=notification.id, actor=current_user)
    return _detail(db, row)


@router.post(
    "/{association_id}/arc-applications/{application_id}/member-fee/reverse",
    response_model=HOAARCApplicationDetailOut,
)
def reverse_arc_member_fee(
    association_id: int, application_id: int, payload: HOAARCReversalIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, _ = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    if any(
        not permission_allows_user(db, user=current_user, menu_key=key)
        for key in ("ACCOUNTING.CHARGES", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.GL_ACCOUNTS")
    ):
        raise HTTPException(status_code=403, detail="Fee reversal requires accounting permission.")
    row = _row(db, org_id=org, association_id=association.id,
               property_id=payload.property_id, application_id=application_id)
    charge = db.query(HOAARCMemberCharge).join(
        HOAARCDecision, HOAARCDecision.application_id == HOAARCMemberCharge.application_id,
    ).filter(
        HOAARCDecision.application_id == row.id,
        HOAARCDecision.organization_id == org,
        HOAARCMemberCharge.organization_id == org,
        HOAARCMemberCharge.association_id == association.id,
        HOAARCMemberCharge.property_id == payload.property_id,
    ).with_for_update().first()
    if charge is None:
        raise HTTPException(status_code=404, detail="ARC member fee not found.")
    if (
        charge.reversal_transaction_id is not None or charge.status != "OPEN"
        or charge.amount_paid != Decimal("0")
    ):
        raise HTTPException(status_code=409, detail="Fee already reversed or partially paid.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == charge.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if original is None:
        raise HTTPException(status_code=409, detail="Original fee GL transaction cannot be reversed.")
    if (
        original.source_type != "hoa_arc_member_charge"
        or original.source_id != db.query(HOAARCDecision.id).filter(
            HOAARCDecision.organization_id == org,
            HOAARCDecision.application_id == row.id,
        ).scalar()
    ):
        raise HTTPException(status_code=409, detail="Original fee source does not match decision.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Reversal must be on or after posting, and not future-dated.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == org,
        GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2:
        raise HTTPException(status_code=409, detail="Unexpected original fee posting shape.")
    try:
        reverse = post_transaction(
            db, organization_id=org,
            transaction_date=payload.reversal_on,
            transaction_type="REVERSAL",
            memo="HOA ARC fee reversal",
            lines=[
                PostingLine(
                    gl_account_id=e.gl_account_id, property_id=e.property_id,
                    unit_id=e.unit_id, owner_id=e.owner_id,
                    debit=e.credit, credit=e.debit,
                )
                for e in entries
            ],
            created_by=current_user, source_type="hoa_arc_member_charge",
            source_id=charge.id, reversal_of_id=original.id,
            commit=False, write_audit=False,
        )
        original.is_reversed = True
        charge.reversal_transaction_id = reverse.id
        charge.status = "REVERSED"
        charge.reversal_reason = payload.reason.strip()
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_arc_member_charge", entity_id=charge.id,
            action="fee_reversed",
            new_value={
                "association_id": association.id, "property_id": payload.property_id,
                "original_gl_transaction_id": original.id,
                "reversal_gl_transaction_id": reverse.id,
                "reversal_on": payload.reversal_on.isoformat(),
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Fee reversal posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent fee reversal.") from exc
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
    org, association, _ = _board_scope(
        db, actor=current_user, association_id=association_id, property_id=property_id,
    )
    if not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.CHARGES"):
        raise HTTPException(status_code=403, detail="Member ledger permission required.")
    row = _row(db, org_id=org, association_id=association.id,
               property_id=property_id, application_id=application_id)
    charge = db.query(HOAARCMemberCharge).join(
        HOAARCDecision, HOAARCDecision.application_id == HOAARCMemberCharge.application_id,
    ).filter(
        HOAARCDecision.application_id == row.id,
        HOAARCMemberCharge.organization_id == org,
        HOAARCMemberCharge.association_id == association.id,
        HOAARCMemberCharge.property_id == property_id,
    ).first()
    response.headers["Cache-Control"] = "no-store"
    if charge is None:
        return {"member_charge": None}
    return {"member_charge": {
        "id": charge.id, "member_user_id": charge.member_user_id,
        "amount": str(charge.amount), "amount_paid": str(charge.amount_paid),
        "due_on": charge.due_on.isoformat(), "status": charge.status,
        "gl_transaction_id": charge.gl_transaction_id,
        "reversal_transaction_id": charge.reversal_transaction_id,
        "reversal_reason": charge.reversal_reason,
    }}
