"""Operational HOA member assessment: explicit board decision, real central GL."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.contact import Contact
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_member_assessment_payment import HOAMemberAssessmentPayment
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.routers import hoa_member_payments as payments_api
from app.routers import hoa_member_statements as statement_api
from app.routers import hoa_annual_budgets as budget_api
from app.models.hoa_annual_budget import HOAAnnualBudget
from app.schemas.hoa_annual_budget import (
    HOAAnnualBudgetCreateIn, HOAAnnualBudgetReviseIn,
    HOAAnnualBudgetDecisionIn,
)
from app.models.entity_attachment import EntityAttachment
from app.schemas.hoa_member_payment import HOAMemberPaymentIn, HOAMemberPaymentReverseIn
from app.schemas.receipt import ReceiptCreateIn
from app.services.receipt_posting import reverse_receipt, process_nsf_receipt
from app.services.gl_posting import PostingError
from app.models.hoa_member_assessment import HOAAssessmentDecision, HOAMemberAssessmentCharge
from app.models.lease import RentInvoice
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_assessments as plans
from app.routers import hoa_payer_drafts as payer_api
from app.routers import hoa_planned_occurrences as occurrences
from app.routers import hoa_board as board_api
from app.routers import hoa_arc_board_decisions as arc_board
from app.routers import hoa_member_assessments as member_api
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.schemas.hoa_assessment import HOAAssessmentProposalIn
from app.schemas.hoa_payer_draft import HOAPayerDraftIn
from app.schemas.hoa_planned_occurrence import HOAPlanGenerationIn
from app.schemas.hoa_board import HOABoardSeatIn, HOABoardAuthorizationIn
from app.schemas.hoa_member_assessment import (
    HOAAssessmentBoardDecisionIn, HOAChargeIssueIn, HOAChargeReverseIn,
)
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
    ])
    monkeypatch.setattr(arc_board, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=key, release_allowed=True,
                        entitlement_allowed=True, org_config_allowed=True)
        for key in arc_board.HOA_GATES
    ])
    monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Assessment Real", slug="assessment-real")
    foreign_org = Organization(name="Assessment Foreign", slug="assessment-foreign")
    db.add_all([org, foreign_org]); db.flush()
    users = []
    for scope, role, name in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "member"),
        (foreign_org, UserRole.ADMIN, "foreign"),
    ):
        user = User(
            organization_id=scope.id, role=role,
            first_name=name, last_name="Assessment",
            email="assessment-real-" + name + "@example.test",
            hashed_password="x", is_active=True,
            is_verified=name in {"admin", "member"},
        )
        db.add(user); users.append(user)
    db.flush()
    props = []
    for scope, name in ((org, "Assigned"), (org, "Other"), (foreign_org, "Foreign")):
        prop = Property(organization_id=scope.id, name=name,
                        address_line1="100 Test", city="Cleveland",
                        state="OH", zip_code="44113", is_active=True)
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    admin, owner, manager, member, foreign = users
    prop, other, outside = props
    association = hoa.create_association(
        HOAAssociationIn(name="Recorded Association", property_ids=[prop.id, other.id]),
        db=db, current_user=admin,
    )
    for user, name in ((admin, "Board chair"), (member, "Responsible member")):
        contact = Contact(
            organization_id=org.id, display_name=name, email=user.email,
            contact_type="PERSON", is_active=True,
        )
        db.add(contact); db.flush()
        link = hoa.add_contact_link(
            association.id, HOAContactLinkIn(
                property_id=prop.id, contact_id=contact.id,
            ), db=db, current_user=admin,
        )
        if user.id == admin.id:
            board_link = link
        else:
            payer_link = link
    seat = board_api.record_board_seat(
        association.id, HOABoardSeatIn(
            property_id=prop.id, contact_link_id=board_link.id,
            proposed_role="CHAIR", staff_voting_eligible=True,
        ), db=db, current_user=admin,
    )
    board_api.authorize_board_seat(
        association.id, seat.id, HOABoardAuthorizationIn(
            property_id=prop.id, user_id=admin.id, can_record_offline=True,
        ), db=db, current_user=admin,
    )
    proposal = plans.create_proposal(
        association.id, HOAAssessmentProposalIn(
            property_id=prop.id, title="Board-confirmed common area dues",
            assessment_type="RECURRING", frequency="QUARTERLY",
            proposed_amount="125.50", proposed_first_on=date(2027, 1, 1),
        ), db=db, current_user=admin,
    )
    payer_api.set_payer_draft(
        association.id, proposal.id, HOAPayerDraftIn(
            property_id=prop.id, contact_link_id=payer_link.id,
        ), db=db, current_user=admin,
    )
    planned = occurrences.generate_occurrences(
        association.id, proposal.id, HOAPlanGenerationIn(
            property_id=prop.id, date_from=date(2027, 1, 1),
            date_to=date(2027, 1, 1),
        ), db=db, current_user=admin,
    )
    ar = GLAccount(
        organization_id=org.id, gl_number="HOA-AR",
        name="HOA member receivable", account_type="ASSET", is_active=True,
    )
    income = GLAccount(
        organization_id=org.id, gl_number="HOA-INCOME",
        name="HOA assessment income", account_type="INCOME", is_active=True,
    )
    db.add_all([ar, income]); db.commit()
    return users, props, association, proposal, payer_link, seat, planned.rows[0], ar, income


def _decision(prop, payer, member, **changes):
    values = dict(
        property_id=prop.id, decision="APPROVED",
        decision_note="The association board adopted this assessment.",
        contact_link_id=payer.id, member_user_id=member.id,
    )
    values.update(changes)
    return HOAAssessmentBoardDecisionIn(**values)


def _issue(prop, member, ar, income, **changes):
    values = dict(
        property_id=prop.id, member_user_id=member.id, due_on=date(2027, 2, 1),
        receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
    )
    values.update(changes)
    return HOAChargeIssueIn(**values)


def test_explicit_board_approval_posts_one_member_receivable_reverses_gl():
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, plan, payer, seat, period, ar, income = _seed(db)
        approve = member_api.record_assessment_decision(
            assoc.id, plan.id, _decision(prop, payer, member),
            db=db, current_user=admin,
        )
        assert approve.decision == "APPROVED" and approve.board_seat_id == seat.id
        assert approve.member_user_id == member.id
        assert approve.approved_amount == Decimal("125.50")
        assert db.query(GLTransaction).count() == 0
        response = Response()
        fetched = member_api.get_assessment_decision(
            assoc.id, plan.id, response, prop.id, db=db, current_user=owner,
        )
        assert fetched.id == approve.id and response.headers["cache-control"] == "no-store"
        for action in (
            lambda: plans.update_proposal(
                assoc.id, plan.id,
                HOAAssessmentProposalIn(
                    property_id=prop.id, title="Changed after approval",
                    assessment_type="RECURRING", frequency="QUARTERLY",
                    proposed_amount="999", proposed_first_on=date(2027, 1, 1),
                ), db=db, current_user=owner,
            ),
            lambda: plans.archive_proposal(
                assoc.id, plan.id, prop.id, db=db, current_user=owner,
            ),
            lambda: member_api.record_assessment_decision(
                assoc.id, plan.id, _decision(prop, payer, member),
                db=db, current_user=admin,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                action()
            assert exc.value.status_code == 409
        issued = member_api.issue_assessment(
            assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
            db=db, current_user=owner,
        )
        assert issued.amount == Decimal("125.50")
        assert issued.member_user_id == member.id and issued.status == "OPEN"
        assert issued.member_receivable and issued.tenant_charge_inferred is False
        txn = db.get(GLTransaction, issued.gl_transaction_id)
        assert txn.source_type == "hoa_member_assessment_charge"
        assert txn.source_id == period.id
        entries = db.query(GLEntry).filter(GLEntry.transaction_id == txn.id).all()
        assert len(entries) == 2
        assert sum((x.debit for x in entries), Decimal("0")) == Decimal("125.50")
        assert sum((x.credit for x in entries), Decimal("0")) == Decimal("125.50")
        assert {x.gl_account_id for x in entries} == {ar.id, income.id}
        assert all(x.property_id == prop.id for x in entries)
        assert db.query(Charge).count() == db.query(RentInvoice).count() == 0
        again = member_api.issue_assessment(
            assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
            db=db, current_user=admin,
        )
        assert again.id == issued.id and db.query(GLTransaction).count() == 1
        with pytest.raises(HTTPException) as conflict:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id,
                _issue(prop, member, ar, income, due_on=date(2027, 2, 2)),
                db=db, current_user=admin,
            )
        assert conflict.value.status_code == 409
        with pytest.raises(HTTPException) as voided:
            occurrences.void_occurrence(
                assoc.id, plan.id, period.id, prop.id,
                db=db, current_user=admin,
            )
        assert voided.value.status_code == 409
        history = member_api.list_member_assessments(
            assoc.id, plan.id, Response(), prop.id,
            db=db, current_user=admin,
        )
        assert [x.id for x in history] == [issued.id]
        reverse = member_api.reverse_assessment(
            assoc.id, plan.id, issued.id,
            HOAChargeReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Board-recorded assessment adjustment",
            ), db=db, current_user=admin,
        )
        assert reverse.status == "REVERSED"
        assert db.query(GLTransaction).count() == 2
        assert db.get(GLTransaction, txn.id).is_reversed is True
        assert reverse.reversal_transaction_id is not None
        with pytest.raises(HTTPException) as duplicate_reverse:
            member_api.reverse_assessment(
                assoc.id, plan.id, issued.id,
                HOAChargeReverseIn(property_id=prop.id, reversal_on=date.today(), reason="again"),
                db=db, current_user=admin,
            )
        assert duplicate_reverse.value.status_code == 409
        assert db.query(GLTransaction).count() == 2
        assert db.query(Charge).count() == db.query(RentInvoice).count() == 0
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_member_assessment_charge",
        ).count() == 2
        for forbidden in ("hoa_assessment_decisions", "hoa_member_assessment_charges"):
            with pytest.raises(HTTPException):
                _model_for_table(forbidden)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_assessment_payer_scope_locked_period_and_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, plan, payer, seat, period, ar, income = _seed(db)
        for actor in (owner, manager, member, foreign):
            with pytest.raises(HTTPException):
                member_api.record_assessment_decision(
                    assoc.id, plan.id, _decision(prop, payer, member),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            member_api.record_assessment_decision(
                assoc.id, plan.id, _decision(other, payer, member),
                db=db, current_user=admin,
            )
        member.is_verified = False; db.flush()
        with pytest.raises(HTTPException) as unverified:
            member_api.record_assessment_decision(
                assoc.id, plan.id, _decision(prop, payer, member),
                db=db, current_user=admin,
            )
        assert unverified.value.status_code == 409
        member.is_verified = True; db.flush()
        with pytest.raises(HTTPException) as bad_member:
            member_api.record_assessment_decision(
                assoc.id, plan.id, _decision(prop, payer, admin),
                db=db, current_user=admin,
            )
        assert bad_member.value.status_code == 409
        approved = member_api.record_assessment_decision(
            assoc.id, plan.id, _decision(prop, payer, member),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as not_member:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id, _issue(prop, admin, ar, income),
                db=db, current_user=admin,
            )
        assert not_member.value.status_code == 409
        for actor in (manager, member, foreign):
            with pytest.raises(HTTPException):
                member_api.issue_assessment(
                    assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as outside:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id,
                _issue(other, member, ar, income),
                db=db, current_user=admin,
            )
        assert outside.value.status_code == 404
        org = db.get(Organization, admin.organization_id)
        org.locked_through_date = date.today()
        db.flush()
        with pytest.raises(HTTPException) as locked:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id,
                _issue(prop, member, ar, income),
                db=db, current_user=admin,
            )
        assert locked.value.status_code == 409
        assert db.query(GLTransaction).count() == 0
        org.locked_through_date = None; db.commit()
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as permissions:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id,
                _issue(prop, member, ar, income),
                db=db, current_user=admin,
            )
        assert permissions.value.status_code == 403
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        member.is_verified = False; db.flush()
        with pytest.raises(HTTPException) as identity:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id,
                _issue(prop, member, ar, income),
                db=db, current_user=admin,
            )
        assert identity.value.status_code == 409
        assert db.query(GLTransaction).count() == db.query(HOAMemberAssessmentCharge).count() == 0
        assert db.query(HOAAssessmentDecision).count() == 1
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_board_denial_offline_evidence_and_input_constraints():
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, _, _), assoc, plan, payer, seat, period, ar, income = _seed(db)
        for invalid in (
            dict(property_id=prop.id, decision="APPROVED", decision_note="Yes"),
            dict(property_id=prop.id, decision="DENIED", decision_note="No",
                 member_user_id=member.id, contact_link_id=payer.id),
            dict(property_id=prop.id, decision="APPROVED", decision_note="Yes",
                 member_user_id=member.id, contact_link_id=payer.id, legally_verified=True),
        ):
            with pytest.raises(ValidationError):
                HOAAssessmentBoardDecisionIn(**invalid)
        decision = member_api.record_assessment_decision(
            assoc.id, plan.id,
            HOAAssessmentBoardDecisionIn(
                property_id=prop.id, decision="DENIED",
                decision_note="Association board declined the proposed assessment.",
            ), db=db, current_user=admin,
        )
        assert decision.decision == "DENIED" and decision.member_user_id is None
        assert db.query(GLTransaction).count() == 0
        with pytest.raises(HTTPException) as denied:
            member_api.issue_assessment(
                assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
                db=db, current_user=admin,
            )
        assert denied.value.status_code == 409
        assert db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def _member_payment(prop, member, cash, *, key="hoa-member-receipt-0001",
                    amount="40.00", reference="CHECK-1001", **changes):
    values = dict(
        property_id=prop.id, member_user_id=member.id,
        cash_gl_account_id=cash.id, received_on=date.today(),
        amount=amount, payment_reference=reference,
        idempotency_key=key,
    )
    values.update(changes)
    return HOAMemberPaymentIn(**values)


def _payment_reverse(prop, **changes):
    values = dict(
        property_id=prop.id, reversal_on=date.today(),
        reason="Correct the offline member receipt",
    )
    values.update(changes)
    return HOAMemberPaymentReverseIn(**values)


def test_actual_offline_hoa_member_receipt_partial_full_and_atomic_reversal():
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, plan, payer, seat, period, ar, income = _seed(db)
        member_api.record_assessment_decision(
            assoc.id, plan.id, _decision(prop, payer, member),
            db=db, current_user=admin,
        )
        charge = member_api.issue_assessment(
            assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
            db=db, current_user=owner,
        )
        cash = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-CASH",
            name="Received HOA cash", account_type="ASSET",
            include_on_cash_flow=True, is_active=True,
        )
        db.add(cash); db.commit()
        response = Response()
        options = payments_api.receipt_cash_options(
            assoc.id, plan.id, charge.id, response, property_id=prop.id,
            db=db, current_user=owner,
        )
        assert response.headers["cache-control"] == "no-store"
        assert [x.id for x in options] == [cash.id]
        initial_gl = db.query(GLTransaction).count()
        first = payments_api.record_assessment_payment(
            assoc.id, plan.id, charge.id,
            _member_payment(prop, member, cash),
            db=db, current_user=owner,
        )
        assert first.amount == Decimal("40.00") and first.status == "POSTED"
        assert first.manually_recorded and not first.bank_collection_executed
        assert db.get(HOAMemberAssessmentCharge, charge.id).amount_paid == Decimal("40.00")
        assert db.get(HOAMemberAssessmentCharge, charge.id).status == "OPEN"
        original = db.get(Receipt, first.receipt_id)
        assert original.type == "HOA_MEMBER"
        assert original.owner_id is None and original.tenant_user_id is None
        assert original.property_id == prop.id
        assert original.reference_number == "CHECK-1001"
        assert original.income_gl_account_id is None
        assert db.query(ReceiptLine).filter(ReceiptLine.receipt_id == original.id).count() == 1
        payment_gl = db.get(GLTransaction, original.gl_transaction_id)
        assert payment_gl.source_type == "receipt" and payment_gl.source_id == original.id
        entry_rows = db.query(GLEntry).filter(GLEntry.transaction_id == payment_gl.id).all()
        assert {e.gl_account_id for e in entry_rows} == {cash.id, ar.id}
        assert any(e.gl_account_id == cash.id and e.debit == Decimal("40.00") for e in entry_rows)
        assert any(e.gl_account_id == ar.id and e.credit == Decimal("40.00") for e in entry_rows)
        repeated = payments_api.record_assessment_payment(
            assoc.id, plan.id, charge.id,
            _member_payment(prop, member, cash),
            db=db, current_user=admin,
        )
        assert repeated.id == first.id and db.query(GLTransaction).count() == initial_gl + 1
        with pytest.raises(HTTPException) as key_conflict:
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id,
                _member_payment(prop, member, cash, reference="DIFFERENT"),
                db=db, current_user=admin,
            )
        assert key_conflict.value.status_code == 409
        with pytest.raises(HTTPException) as too_large:
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id,
                _member_payment(prop, member, cash, key="hoa-member-receipt-oversize",
                                amount="125.50"),
                db=db, current_user=admin,
            )
        assert too_large.value.status_code == 409
        with pytest.raises(PostingError):
            reverse_receipt(
                db, original=original, reversal_date=date.today(),
                memo="Generic cross-route bypass", created_by=admin,
            )
        with pytest.raises(PostingError):
            process_nsf_receipt(
                db, original=original, process_date=date.today(),
                memo="Generic NSF bypass", created_by=admin,
            )
        second = payments_api.record_assessment_payment(
            assoc.id, plan.id, charge.id,
            _member_payment(prop, member, cash, key="hoa-member-receipt-0002",
                            amount="85.50", reference="CHECK-1002"),
            db=db, current_user=admin,
        )
        assert second.status == "POSTED"
        assert db.get(HOAMemberAssessmentCharge, charge.id).amount_paid == Decimal("125.50")
        assert db.get(HOAMemberAssessmentCharge, charge.id).status == "PAID"
        with pytest.raises(HTTPException) as protected:
            member_api.reverse_assessment(
                assoc.id, plan.id, charge.id,
                HOAChargeReverseIn(
                    property_id=prop.id, reversal_on=date.today(),
                    reason="Cannot undo receivable with paid receipts",
                ), db=db, current_user=admin,
            )
        assert protected.value.status_code == 409
        reversed_second = payments_api.reverse_assessment_payment(
            assoc.id, plan.id, charge.id, second.id,
            _payment_reverse(prop), db=db, current_user=owner,
        )
        assert reversed_second.status == "REVERSED"
        assert reversed_second.reversal_receipt_id != second.receipt_id
        assert db.get(HOAMemberAssessmentCharge, charge.id).status == "OPEN"
        assert db.get(HOAMemberAssessmentCharge, charge.id).amount_paid == Decimal("40.00")
        assert db.get(Receipt, second.receipt_id).is_reversed is True
        assert db.get(GLTransaction, db.get(Receipt, second.receipt_id).gl_transaction_id).is_reversed
        with pytest.raises(HTTPException) as replay:
            payments_api.reverse_assessment_payment(
                assoc.id, plan.id, charge.id, second.id,
                _payment_reverse(prop), db=db, current_user=admin,
            )
        assert replay.value.status_code == 409
        reversed_first = payments_api.reverse_assessment_payment(
            assoc.id, plan.id, charge.id, first.id,
            _payment_reverse(prop), db=db, current_user=admin,
        )
        assert reversed_first.status == "REVERSED"
        assert db.get(HOAMemberAssessmentCharge, charge.id).amount_paid == Decimal("0.00")
        assert db.query(GLTransaction).count() == initial_gl + 4
        assert db.query(Receipt).count() == 4
        assert db.query(HOAMemberAssessmentPayment).count() == 2
        assert db.query(Charge).count() == db.query(RentInvoice).count() == 0
        response = Response()
        history = payments_api.list_assessment_payments(
            assoc.id, plan.id, charge.id, response, property_id=prop.id,
            db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert len(history) == 2 and all(p.status == "REVERSED" for p in history)
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_member_assessment_payment",
        ).count() == 4
        with pytest.raises(HTTPException):
            _model_for_table("hoa_member_assessment_payments")
        with pytest.raises(ValidationError):
            ReceiptCreateIn(
                type="HOA_MEMBER", receipt_date=date.today(),
                amount=1, cash_gl_account_id=cash.id,
            )
        member_api.reverse_assessment(
            assoc.id, plan.id, charge.id,
            HOAChargeReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Approved correction after payment reversal",
            ), db=db, current_user=admin,
        )
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_hoa_member_receipt_scopes_member_identity_cash_and_locked_period(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, plan, payer, seat, period, ar, income = _seed(db)
        member_api.record_assessment_decision(
            assoc.id, plan.id, _decision(prop, payer, member),
            db=db, current_user=admin,
        )
        charge = member_api.issue_assessment(
            assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
            db=db, current_user=owner,
        )
        cash = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-CASH-2",
            name="Recorded cash", account_type="ASSET",
            include_on_cash_flow=True, is_active=True,
        )
        db.add(cash); db.commit()
        payload = _member_payment(prop, member, cash)
        for actor in (manager, member, foreign):
            with pytest.raises(HTTPException):
                payments_api.record_assessment_payment(
                    assoc.id, plan.id, charge.id, payload,
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id, _member_payment(other, member, cash),
                db=db, current_user=admin,
            )
        with pytest.raises(HTTPException):
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id,
                _member_payment(prop, foreign, cash),
                db=db, current_user=admin,
            )
        with pytest.raises(HTTPException):
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id,
                _member_payment(prop, member, ar),
                db=db, current_user=admin,
            )
        with pytest.raises(HTTPException):
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id,
                _member_payment(prop, member, cash, received_on=date(2030, 1, 1)),
                db=db, current_user=admin,
            )
        member.is_verified = False; db.flush()
        with pytest.raises(HTTPException):
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id, payload,
                db=db, current_user=admin,
            )
        member.is_verified = True; db.flush()
        from app.models.user import Organization
        org = db.get(Organization, admin.organization_id)
        org.locked_through_date = date.today()
        db.flush()
        with pytest.raises(HTTPException) as locked:
            payments_api.record_assessment_payment(
                assoc.id, plan.id, charge.id, payload,
                db=db, current_user=admin,
            )
        assert locked.value.status_code == 409
        assert db.query(Receipt).count() == 0
        assert db.query(GLTransaction).count() == 1
        org.locked_through_date = None
        db.flush()
        receipt = payments_api.record_assessment_payment(
            assoc.id, plan.id, charge.id, payload,
            db=db, current_user=admin,
        )
        assert receipt.status == "POSTED"
        org.locked_through_date = date.today()
        db.flush()
        with pytest.raises(HTTPException) as closed:
            payments_api.reverse_assessment_payment(
                assoc.id, plan.id, charge.id, receipt.id,
                _payment_reverse(prop), db=db, current_user=admin,
            )
        assert closed.value.status_code == 409
        assert db.get(HOAMemberAssessmentPayment, receipt.id).status == "POSTED"
        org.locked_through_date = None
        db.flush()
        db.query(HOAMemberAssessmentPayment).filter(
            HOAMemberAssessmentPayment.id == receipt.id,
        ).one()
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException):
            payments_api.list_assessment_payments(
                assoc.id, plan.id, charge.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
    finally:
        db.rollback(); db.close(); engine.dispose()

def test_actual_member_statements_reconcile_receipts_reversals_and_scopes(monkeypatch):
    """Account statements reflect only actual member postings, across proposals."""
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, plan, payer, seat, period, ar, income = _seed(db)
        assert statement_api.member_statements(
            assoc.id, Response(), property_id=prop.id, db=db, current_user=admin,
        ) == []
        member_api.record_assessment_decision(
            assoc.id, plan.id, _decision(prop, payer, member),
            db=db, current_user=admin,
        )
        charge = member_api.issue_assessment(
            assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
            db=db, current_user=owner,
        )
        before = (db.query(Charge).count(), db.query(RentInvoice).count(),
                  db.query(GLTransaction).count(), db.query(Receipt).count(),
                  db.query(AuditLog).count())
        response = Response()
        rows = statement_api.member_statements(
            assoc.id, response, property_id=prop.id,
            db=db, current_user=owner,
        )
        assert response.headers["cache-control"] == "no-store"
        assert len(rows) == 1 and rows[0].member_user_id == member.id
        assert rows[0].total_assessed == Decimal("125.50")
        assert rows[0].total_paid == Decimal("0.00")
        assert rows[0].outstanding == Decimal("125.50")
        assert rows[0].charges[0].status == "OPEN"
        assert len(rows[0].charges[0].payments) == 0
        assert statement_api.member_statements(
            assoc.id, Response(), property_id=prop.id, member_user_id=admin.id,
            db=db, current_user=admin,
        ) == []
        cash = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-STATEMENT-CASH",
            name="Statement test cash", account_type="ASSET",
            include_on_cash_flow=True, is_active=True,
        )
        db.add(cash); db.commit()
        first = payments_api.record_assessment_payment(
            assoc.id, plan.id, charge.id, _member_payment(prop, member, cash),
            db=db, current_user=admin,
        )
        rows = statement_api.member_statements(
            assoc.id, Response(), property_id=prop.id,
            member_user_id=member.id, db=db, current_user=admin,
        )
        assert rows[0].total_paid == Decimal("40.00")
        assert rows[0].outstanding == Decimal("85.50")
        assert len(rows[0].charges[0].payments) == 1
        assert rows[0].charges[0].payments[0].receipt_id == first.receipt_id
        assert rows[0].charges[0].payments[0].status == "POSTED"
        payments_api.reverse_assessment_payment(
            assoc.id, plan.id, charge.id, first.id, _payment_reverse(prop),
            db=db, current_user=owner,
        )
        rows = statement_api.member_statements(
            assoc.id, Response(), property_id=prop.id,
            db=db, current_user=admin,
        )
        assert rows[0].total_paid == Decimal("0.00")
        assert rows[0].outstanding == Decimal("125.50")
        assert rows[0].charges[0].payments[0].status == "REVERSED"
        assert rows[0].charges[0].payments[0].reversal_receipt_id is not None
        member_api.reverse_assessment(
            assoc.id, plan.id, charge.id,
            HOAChargeReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Account statement cancellation test",
            ), db=db, current_user=admin,
        )
        rows = statement_api.member_statements(
            assoc.id, Response(), property_id=prop.id,
            db=db, current_user=admin,
        )
        assert rows[0].total_assessed == Decimal("0.00")
        assert rows[0].total_paid == Decimal("0.00")
        assert rows[0].outstanding == Decimal("0.00")
        assert rows[0].charges[0].status == "REVERSED"
        assert rows[0].charges[0].reversal_transaction_id is not None
        for actor, property_id in (
            (manager, prop.id), (member, prop.id),
            (foreign, prop.id), (admin, outside.id),
            (manager, other.id),
        ):
            with pytest.raises(HTTPException):
                statement_api.member_statements(
                    assoc.id, Response(), property_id=property_id,
                    db=db, current_user=actor,
                )
        monkeypatch.setattr(member_api, "permission_allows_user",
                            lambda *args, **kwargs: False)
        with pytest.raises(HTTPException) as denied:
            statement_api.member_statements(
                assoc.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
        assert denied.value.status_code == 403
        monkeypatch.setattr(member_api, "permission_allows_user",
                            lambda *args, **kwargs: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *args, **kwargs: [])
        with pytest.raises(HTTPException):
            statement_api.member_statements(
                assoc.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
        assert db.query(Charge).count() == before[0]
        assert db.query(RentInvoice).count() == before[1]
        assert db.query(GLTransaction).count() == before[2] + 3
        assert db.query(Receipt).count() == before[3] + 2
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_member_statement_detects_inconsistent_accounting_without_mutation():
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, plan, payer, seat, period, ar, income = _seed(db)
        member_api.record_assessment_decision(
            assoc.id, plan.id, _decision(prop, payer, member),
            db=db, current_user=admin,
        )
        charge = member_api.issue_assessment(
            assoc.id, plan.id, period.id, _issue(prop, member, ar, income),
            db=db, current_user=admin,
        )
        stored = db.get(HOAMemberAssessmentCharge, charge.id)
        stored.amount_paid = Decimal("10.00")
        db.flush()
        with pytest.raises(HTTPException) as mismatch:
            statement_api.member_statements(
                assoc.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
        assert mismatch.value.status_code == 409
        assert db.query(GLTransaction).count() == 1
        assert db.query(Receipt).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def _annual(prop, income, expense, *, year=2029, reserve="25.00",
            text="Association operating plan"):
    return HOAAnnualBudgetCreateIn(
        property_id=prop.id, calendar_year=year, description=text,
        lines=[
            dict(gl_account_id=income.id, annual_amount="300.00"),
            dict(gl_account_id=expense.id, annual_amount="125.00"),
        ],
        reserve_allocation=reserve,
    )


def test_hoa_annual_budget_operational_board_approval_versions_and_snapshots():
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, proposal, payer, seat, period, income_ar, income = _seed(db)
        expense = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-BUDGET-EXP",
            name="HOA maintenance expense", account_type="EXPENSE", is_active=True,
        )
        db.add(expense); db.commit()
        initial = (db.query(Charge).count(), db.query(GLTransaction).count(),
                   db.query(Receipt).count(), db.query(RentInvoice).count())
        options = budget_api.annual_budget_accounts(
            assoc.id, Response(), property_id=prop.id, db=db, current_user=admin,
        )
        assert {x.id for x in options} >= {income.id, expense.id}
        payload = _annual(prop, income, expense)
        budget = budget_api.create_annual_budget(
            assoc.id, payload, db=db, current_user=admin,
        )
        assert budget.status == "DRAFT"
        assert budget.revision == budget.version == 1
        assert budget.total_income == Decimal("300.00")
        assert budget.total_expense == Decimal("125.00")
        assert budget.reserve_allocation == Decimal("25.00")
        assert budget.member_assessment_issued is False
        assert budget.reserve_cash_transferred is False
        duplicate = budget_api.create_annual_budget(
            assoc.id, payload, db=db, current_user=owner,
        )
        assert duplicate.id == budget.id
        with pytest.raises(HTTPException) as conflict:
            budget_api.create_annual_budget(
                assoc.id, _annual(prop, income, expense, text="Different draft"),
                db=db, current_user=admin,
            )
        assert conflict.value.status_code == 409
        with pytest.raises(ValidationError):
            HOAAnnualBudgetCreateIn(
                property_id=prop.id, calendar_year=2029,
                description="Duplicated GL",
                lines=[
                    dict(gl_account_id=expense.id, annual_amount="15.00"),
                    dict(gl_account_id=expense.id, annual_amount="15.00"),
                ], reserve_allocation="0.00",
            )
        with pytest.raises(HTTPException) as reserve:
            budget_api.create_annual_budget(
                assoc.id, _annual(prop, income, expense, reserve="126.00"),
                db=db, current_user=admin,
            )
        assert reserve.value.status_code == 422
        revised = budget_api.revise_annual_budget(
            assoc.id, budget.id,
            HOAAnnualBudgetReviseIn(
                **_annual(prop, income, expense, reserve="20.00").model_dump(),
                expected_version=1,
            ), db=db, current_user=admin,
        )
        assert revised.version == 2 and revised.reserve_allocation == Decimal("20.00")
        with pytest.raises(HTTPException) as stale:
            budget_api.revise_annual_budget(
                assoc.id, budget.id,
                HOAAnnualBudgetReviseIn(
                    **_annual(prop, income, expense).model_dump(),
                    expected_version=1,
                ), db=db, current_user=admin,
            )
        assert stale.value.status_code == 409
        for actor in (owner, manager, member, foreign):
            with pytest.raises(HTTPException):
                budget_api.decide_annual_budget(
                    assoc.id, budget.id,
                    HOAAnnualBudgetDecisionIn(
                        property_id=prop.id, expected_version=2,
                        decision="APPROVED", decision_note="Adopted annual operating budget",
                    ), db=db, current_user=actor,
                )
        approved = budget_api.decide_annual_budget(
            assoc.id, budget.id,
            HOAAnnualBudgetDecisionIn(
                property_id=prop.id, expected_version=2,
                decision="APPROVED", decision_note="Adopted annual operating budget",
            ), db=db, current_user=admin,
        )
        assert approved.status == "APPROVED" and approved.version == 3
        assert approved.decision_method == "DIRECT"
        assert approved.board_seat_id == seat.id
        assert approved.decided_on == date.today()
        assert approved.total_income == Decimal("300.00")
        assert approved.lines[1].annual_amount == Decimal("125.00") or approved.lines[0].annual_amount == Decimal("125.00")
        with pytest.raises(HTTPException) as immutable:
            budget_api.revise_annual_budget(
                assoc.id, budget.id,
                HOAAnnualBudgetReviseIn(
                    **_annual(prop, income, expense).model_dump(),
                    expected_version=3,
                ), db=db, current_user=owner,
            )
        assert immutable.value.status_code == 409
        later = budget_api.create_annual_budget(
            assoc.id, _annual(prop, income, expense, text="Board amendment budget"),
            db=db, current_user=owner,
        )
        assert later.id != budget.id and later.revision == 2
        assert approved.revision == 1
        denial = budget_api.decide_annual_budget(
            assoc.id, later.id,
            HOAAnnualBudgetDecisionIn(
                property_id=prop.id, expected_version=1,
                decision="DENIED", decision_note="Association did not adopt amendment",
            ), db=db, current_user=admin,
        )
        assert denial.status == "DENIED"
        response = Response()
        history = budget_api.list_annual_budgets(
            assoc.id, response, property_id=prop.id,
            calendar_year=2029, db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert [x.revision for x in history] == [2, 1]
        assert [x.status for x in history] == ["DENIED", "APPROVED"]
        assert budget_api.list_annual_budgets(
            assoc.id, Response(), property_id=prop.id,
            calendar_year=2030, db=db, current_user=admin,
        ) == []
        assert (db.query(Charge).count(), db.query(GLTransaction).count(),
                db.query(Receipt).count(), db.query(RentInvoice).count()) == initial
        audit = db.query(AuditLog).filter(AuditLog.entity_type == "hoa_annual_budget").all()
        assert len(audit) == 5
        assert all("Association operating plan" not in (x.new_value or "") for x in audit)
        assert all("300.00" not in (x.new_value or "") for x in audit)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_annual_budgets")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_hoa_annual_budget_offline_scope_archive_and_unauthorized_gl(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, member, foreign), (prop, other, outside), assoc, proposal, payer, seat, period, ar, income = _seed(db)
        expense = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-BUDGET-OPS",
            name="Annual operations", account_type="EXPENSE", is_active=True,
        )
        foreign_expense = GLAccount(
            organization_id=foreign.organization_id, gl_number="FOREIGN-BUDGET",
            name="Not a permitted account", account_type="EXPENSE", is_active=True,
        )
        db.add_all([expense, foreign_expense]); db.commit()
        bad_lines = HOAAnnualBudgetCreateIn(
            property_id=prop.id, calendar_year=2029,
            description="Unauthorized GL", reserve_allocation="0.00",
            lines=[dict(gl_account_id=foreign_expense.id, annual_amount="5.00")],
        )
        with pytest.raises(HTTPException) as no_foreign_account:
            budget_api.create_annual_budget(
                assoc.id, bad_lines, db=db, current_user=admin,
            )
        assert no_foreign_account.value.status_code == 404
        original = _annual(prop, income, expense)
        for actor, p in ((manager, prop), (member, prop), (foreign, prop),
                         (admin, outside), (manager, other)):
            with pytest.raises(HTTPException):
                budget_api.create_annual_budget(
                    assoc.id, HOAAnnualBudgetCreateIn(**{
                        **original.model_dump(), "property_id": p.id,
                    }), db=db, current_user=actor,
                )
        saved = budget_api.create_annual_budget(
            assoc.id, original, db=db, current_user=admin,
        )
        for actor, p in ((member, prop), (foreign, prop), (manager, other),
                         (admin, outside)):
            with pytest.raises(HTTPException):
                budget_api.list_annual_budgets(
                    assoc.id, Response(), property_id=p.id,
                    calendar_year=2029, db=db, current_user=actor,
                )
        # Verified board login is allowed to read its own budget even
        # when it does not hold all staff-wide accounting permissions.
        monkeypatch.setattr(budget_api, "permission_allows_user", lambda *a, **kw: False)
        assert budget_api.list_annual_budgets(
            assoc.id, Response(), property_id=prop.id,
            calendar_year=2029, db=db, current_user=admin,
        )[0].id == saved.id
        monkeypatch.setattr(budget_api, "permission_allows_user", lambda *a, **kw: True)
        private = EntityAttachment(
            organization_id=admin.organization_id,
            entity_type="properties", entity_id=prop.id,
            storage_key="synthetic-annual-board.pdf",
            original_name="synthetic-annual-board.pdf",
            content_type="application/pdf", size_bytes=100,
            is_active=True, share_with_owners=False, share_with_tenants=False,
        )
        db.add(private); db.commit()
        approved = budget_api.decide_annual_budget(
            assoc.id, saved.id, HOAAnnualBudgetDecisionIn(
                property_id=prop.id, expected_version=1,
                decision="APPROVED", decision_note="Offline board adoption recorded",
                offline_meeting_on=date.today(), decision_maker_seat_id=seat.id,
                supporting_attachment_id=private.id,
            ), db=db, current_user=admin,
        )
        assert approved.decision_method == "OFFLINE"
        assert approved.decision_maker_seat_id == seat.id
        assert approved.status == "APPROVED"
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded Association", property_ids=[other.id],
            ), db=db, current_user=owner,
        )
        assert db.get(HOAAnnualBudget, saved.id).is_active is False
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded Association", property_ids=[prop.id, other.id],
            ), db=db, current_user=owner,
        )
        assert budget_api.list_annual_budgets(
            assoc.id, Response(), property_id=prop.id,
            calendar_year=2029, db=db, current_user=admin,
        ) == []
        replacement = budget_api.create_annual_budget(
            assoc.id, original, db=db, current_user=admin,
        )
        assert replacement.id != saved.id
        assert db.get(HOAAnnualBudget, saved.id).status == "APPROVED"
        assert db.query(GLTransaction).count() == 0
        assert db.query(Charge).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
