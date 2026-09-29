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
