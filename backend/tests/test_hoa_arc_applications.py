"""HOA ARC review and recorded board decisions remain scoped and auditable."""
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
from app.models.gl_account import GLAccount
from app.models.hoa_arc_decision import HOAARCDecision, HOAARCMemberCharge
from app.models.hoa_board import HOABoardSeat
from app.models.lease import Lease, LeaseStatus
from app.models.property import Unit
from app.models.work_order import WorkOrder
from app.routers import hoa_arc_board_decisions as board_api
from app.routers import hoa_board as hoa_board_api
from app.schemas.hoa_arc_application import HOAARCDecisionIn, HOAARCDecisionFeeIn
from app.schemas.hoa_board import HOABoardSeatIn
from app.models.contact import Contact
from app.models.entity_attachment import EntityAttachment
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_arc_application import (
    HOAARCApplication, HOAARCApplicationAttachment, HOAARCReviewEvent,
)
from app.models.hoa_arc_intake import HOAARCIntake
from app.models.lease import RentInvoice
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import entity_attachments as attachments
from app.routers import hoa_arc_applications as api
from app.routers import hoa_arc_intake as intake_api
from app.routers import hoa_associations as hoa
from app.schemas.entity_attachment import EntityAttachmentShareUpdate
from app.schemas.hoa_arc_application import (
    HOAARCApplicationIn, HOAARCAttachmentIn, HOAARCReviewEventIn,
)
from app.schemas.hoa_arc_intake import HOAARCIntakeIn
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def access(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
    ])
    monkeypatch.setattr(api, "_require_attachment_feature", lambda *a, **kw: None)
    monkeypatch.setattr(board_api, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(attachments, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=attachments.ATTACHMENTS_FEATURE_KEY, allowed=True)
    ])
    notes = __import__("app.services.entity_notes", fromlist=["permission_allows_user"])
    monkeypatch.setattr(notes, "permission_allows_user", lambda *a, **kw: True)


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="ARC Local", slug="arc-local")
    other = Organization(name="ARC Foreign", slug="arc-foreign")
    db.add_all([org, other]); db.flush()
    users = []
    for scope, role, name in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        row = User(
            organization_id=scope.id, role=role, first_name=name, last_name="ARC",
            email=f"arc-{name}@example.test", hashed_password="x", is_active=True,
        )
        db.add(row); users.append(row)
    db.flush()
    props = []
    for scope, name in ((org, "Assigned"), (org, "Unassigned"), (other, "Foreign")):
        row = Property(
            organization_id=scope.id, name=name, address_line1="100 Main",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(row); props.append(row)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    contacts = []
    for scope, name in ((org, "Applicant One"), (org, "Other Applicant"), (other, "Foreign Applicant")):
        row = Contact(
            organization_id=scope.id, display_name=name, contact_type="PERSON",
            is_active=True, created_by_id=users[0].id if scope.id == org.id else users[4].id,
        )
        db.add(row); contacts.append(row)
    db.flush(); db.commit()
    assoc = hoa.create_association(
        HOAAssociationIn(name="ARC HOA", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0],
    )
    links = [
        hoa.add_contact_link(
            assoc.id, HOAContactLinkIn(property_id=props[i].id, contact_id=contacts[i].id),
            db=db, current_user=users[0],
        )
        for i in (0, 1)
    ]
    intake = intake_api.create_arc_intake(
        assoc.id,
        HOAARCIntakeIn(
            property_id=props[0].id, project_title="Fence replacement",
            staff_noted_on=date(2026, 9, 10), staff_description="Applicant asked about a fence.",
        ),
        db=db, current_user=users[0],
    )
    docs = []
    for prop, name, shared in (
        (props[0], "arc-private.pdf", False),
        (props[0], "arc-shared.pdf", True),
        (props[1], "elsewhere.pdf", False),
    ):
        row = EntityAttachment(
            organization_id=org.id, entity_type="properties", entity_id=prop.id,
            storage_key=f"arc-{name}", original_name=name, content_type="application/pdf",
            size_bytes=100, share_with_tenants=shared, share_with_owners=False,
            is_active=True, uploaded_by_id=users[0].id,
        )
        db.add(row); docs.append(row)
    db.commit()
    return users, props, assoc, links, intake, docs


def _application(prop_id, intake_id, link_id):
    return HOAARCApplicationIn(
        property_id=prop_id, intake_id=intake_id,
        applicant_contact_link_id=link_id, submitted_on=date(2026, 9, 12),
    )


def _counts(db):
    return (
        db.query(Charge).count(), db.query(RentInvoice).count(),
        db.query(GLTransaction).count(), db.query(GLEntry).count(),
    )


def test_arc_application_review_lifecycle_prepares_but_never_issues_decision():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, _, _), assoc, links, intake, docs = _seed(db)
        before = _counts(db)
        created = api.create_application(
            assoc.id, _application(assigned.id, intake.id, links[0].id),
            db=db, current_user=admin,
        )
        assert created.status == "SUBMITTED"
        assert created.board_decision is None
        assert [e.event_type for e in created.events] == ["APPLICATION_SUBMITTED"]

        stages = [
            ("START_REVIEW", "UNDER_REVIEW"),
            ("REQUEST_MORE_INFO", "MORE_INFO_REQUESTED"),
            ("RECORD_INFO_RECEIVED", "INFO_RECEIVED"),
            ("MARK_READY_FOR_DECISION", "READY_FOR_DECISION"),
            ("PREPARE_APPROVAL", "DECISION_PREPARED"),
        ]
        detail = created
        for event_type, status in stages:
            detail = api.add_review_event(
                assoc.id, created.id,
                HOAARCReviewEventIn(event_type=event_type, staff_note=f"Staff {event_type}"),
                property_id=assigned.id, db=db, current_user=owner,
            )
            assert detail.status == status
            assert detail.board_decision is None
        assert detail.decision_preparation == "APPROVE"
        assert len(detail.events) == 6
        assert _counts(db) == before
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_arc_application"
        ).count() == 6
        assert db.query(HOAARCReviewEvent).count() == 6
        with pytest.raises(HTTPException) as exc:
            api.add_review_event(
                assoc.id, created.id,
                HOAARCReviewEventIn(event_type="PREPARE_DENIAL"),
                property_id=assigned.id, db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
    finally:
        db.close(); engine.dispose()


def test_arc_application_private_attachments_scope_and_sharing_guard():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, _), assoc, links, intake, docs = _seed(db)
        application = api.create_application(
            assoc.id, _application(assigned.id, intake.id, links[0].id),
            db=db, current_user=admin,
        )
        linked = api.add_application_attachment(
            assoc.id, application.id, HOAARCAttachmentIn(attachment_id=docs[0].id),
            property_id=assigned.id, db=db, current_user=owner,
        )
        assert linked.filename == "arc-private.pdf" and linked.private_only is True
        detail = api.get_application(
            assoc.id, application.id, Response(), assigned.id,
            db=db, current_user=manager,
        )
        assert [x.attachment_id for x in detail.attachments] == [docs[0].id]
        for bad in (docs[1], docs[2]):
            with pytest.raises(HTTPException) as exc:
                api.add_application_attachment(
                    assoc.id, application.id, HOAARCAttachmentIn(attachment_id=bad.id),
                    property_id=assigned.id, db=db, current_user=admin,
                )
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            attachments.update_entity_attachment_sharing(
                docs[0].id, EntityAttachmentShareUpdate(share_with_owners=True),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        api.archive_application_attachment(
            assoc.id, application.id, linked.id, assigned.id,
            db=db, current_user=admin,
        )
        assert api.get_application(
            assoc.id, application.id, Response(), assigned.id,
            db=db, current_user=manager,
        ).attachments == []
        assert _counts(db) == (0, 0, 0, 0)
    finally:
        db.close(); engine.dispose()


def test_arc_application_role_org_property_and_schema_boundaries(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, outside), assoc, links, intake, docs = _seed(db)
        app = api.create_application(
            assoc.id, _application(assigned.id, intake.id, links[0].id),
            db=db, current_user=admin,
        )
        assert [x.id for x in api.list_applications(
            assoc.id, Response(), assigned.id, db=db, current_user=manager
        )] == [app.id]
        for actor, prop in ((manager, unassigned), (foreign, assigned), (manager, outside)):
            with pytest.raises(HTTPException):
                api.list_applications(assoc.id, Response(), prop.id, db=db, current_user=actor)
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                api.create_application(
                    assoc.id, _application(assigned.id, intake.id, links[0].id),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as exc:
            api.create_application(
                assoc.id, _application(assigned.id, intake.id, links[1].id),
                db=db, current_user=owner,
            )
        assert exc.value.status_code in {404, 409}
        with pytest.raises(ValidationError):
            HOAARCApplicationIn(
                property_id=assigned.id, intake_id=intake.id,
                applicant_contact_link_id=links[0].id,
                submitted_on=date.today(), approved=True,
            )
        with pytest.raises(ValidationError):
            HOAARCReviewEventIn(event_type="ISSUE_APPROVAL")
        for name in ("hoa_arc_applications", "hoa_arc_application_attachments", "hoa_arc_review_events"):
            with pytest.raises(HTTPException):
                _model_for_table(name)
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            api.get_application(
                assoc.id, app.id, Response(), assigned.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        assert _counts(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_arc_application_archive_history_and_no_silent_duplicate():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, _, _), assoc, links, intake, docs = _seed(db)
        app = api.create_application(
            assoc.id, _application(assigned.id, intake.id, links[0].id),
            db=db, current_user=admin,
        )
        api.archive_application(
            assoc.id, app.id, assigned.id, db=db, current_user=owner,
        )
        assert api.list_applications(
            assoc.id, Response(), assigned.id, db=db, current_user=admin
        ) == []
        assert db.query(HOAARCApplication).filter_by(id=app.id).one().is_active is False
        assert db.query(HOAARCReviewEvent).filter_by(application_id=app.id).count() == 1
        with pytest.raises(HTTPException) as exc:
            api.create_application(
                assoc.id, _application(assigned.id, intake.id, links[0].id),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(HOAARCApplication).count() == 1
        assert _counts(db) == (0, 0, 0, 0)
    finally:
        db.close(); engine.dispose()


def _board_member(db, assoc, prop, admin):
    admin.is_verified = True
    contact = Contact(
        organization_id=admin.organization_id,
        display_name="Verified Board Login",
        email=admin.email, contact_type="PERSON", is_active=True,
    )
    db.add(contact)
    db.flush()
    link = hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(
            property_id=prop.id, contact_id=contact.id,
        ), db=db, current_user=admin,
    )
    seat = hoa_board_api.record_board_seat(
        assoc.id, HOABoardSeatIn(
            property_id=prop.id, contact_link_id=link.id,
            proposed_role="DIRECTOR", staff_voting_eligible=True,
        ), db=db, current_user=admin,
    )
    return seat


def _ready_application(db, assoc, prop, intake, applicant_link, admin):
    application = api.create_application(
        assoc.id, _application(prop.id, intake.id, applicant_link.id),
        db=db, current_user=admin,
    )
    for event in ("START_REVIEW", "MARK_READY_FOR_DECISION"):
        api.add_review_event(
            assoc.id, application.id,
            HOAARCReviewEventIn(event_type=event),
            property_id=prop.id, db=db, current_user=admin,
        )
    return application


def test_board_approved_arc_is_final_without_software_legal_effect_flag(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, _, _), assoc, links, intake, _ = _seed(db)
        application = _ready_application(db, assoc, prop, intake, links[0], admin)
        before = _counts(db)
        with pytest.raises(HTTPException) as denied:
            board_api.record_board_decision(
                assoc.id, application.id, HOAARCDecisionIn(
                    property_id=prop.id, decision="APPROVED",
                    decision_note="Board recorded approval",
                ), db=db, current_user=admin,
            )
        assert denied.value.status_code == 403
        seat = _board_member(db, assoc, prop, admin)
        detail = board_api.record_board_decision(
            assoc.id, application.id, HOAARCDecisionIn(
                property_id=prop.id, decision="APPROVED",
                decision_note="Board recorded approval",
            ), db=db, current_user=admin,
        )
        assert detail.status == "APPROVED"
        assert detail.decision_preparation is None
        assert detail.board_decision.decision == "APPROVED"
        assert detail.board_decision.board_seat_id == seat.id
        assert detail.board_decision.notification_status == "NO_VERIFIED_RECIPIENT"
        assert detail.board_decision.member_charge_id is None
        assert "legal_decision_effective" not in detail.model_dump()
        assert "governing_authority_verified" not in detail.model_dump()
        assert [e.event_type for e in detail.events][-1] == "BOARD_APPROVED"
        assert db.query(HOAARCDecision).count() == 1
        assert _counts(db) == before
        for event in ("PREPARE_DENIAL", "REQUEST_MORE_INFO", "START_REVIEW"):
            with pytest.raises(HTTPException) as exc:
                api.add_review_event(
                    assoc.id, application.id, HOAARCReviewEventIn(event_type=event),
                    property_id=prop.id, db=db, current_user=admin,
                )
            assert exc.value.status_code == 409
        with pytest.raises(HTTPException) as conflict:
            board_api.record_board_decision(
                assoc.id, application.id,
                HOAARCDecisionIn(property_id=prop.id, decision="DENIED",
                                 decision_note="Different decision"),
                db=db, current_user=admin,
            )
        assert conflict.value.status_code == 409
        assert db.query(HOAARCDecision).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_arc_decision",
            AuditLog.action == "board_decision_recorded",
        ).count() == 1
        with pytest.raises(HTTPException):
            _model_for_table("hoa_arc_decisions")
        with pytest.raises(HTTPException):
            _model_for_table("hoa_arc_member_charges")
    finally:
        db.close()
        engine.dispose()


def test_arc_approved_fee_uses_member_receivable_gl_and_real_work_order(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, _, _), assoc, links, intake, _ = _seed(db)
        _board_member(db, assoc, prop, admin)
        tenant.is_verified = True
        applicant = db.query(Contact).filter(Contact.id == links[0].contact_id).one()
        applicant.email = tenant.email
        unit = Unit(property_id=prop.id, unit_number="ARC101", is_active=True)
        db.add(unit)
        db.flush()
        db.add(Lease(
            unit_id=unit.id, tenant_id=tenant.id, start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1), monthly_rent=Decimal("1200"),
            security_deposit=Decimal("0"), status=LeaseStatus.ACTIVE,
        ))
        ar = GLAccount(
            organization_id=admin.organization_id, gl_number="E2E-AR-ARC",
            name="ARC member receivable", account_type="ASSET", is_active=True,
        )
        income = GLAccount(
            organization_id=admin.organization_id, gl_number="E2E-INC-ARC",
            name="ARC fee income", account_type="INCOME", is_active=True,
        )
        db.add_all([ar, income])
        db.commit()
        application = _ready_application(db, assoc, prop, intake, links[0], admin)
        sent = []
        monkeypatch.setattr(board_api, "send_email", lambda **kw: sent.append(kw))
        payload = HOAARCDecisionIn(
            property_id=prop.id, decision="APPROVED",
            decision_note="Board approved with scheduled follow-up",
            fee=HOAARCDecisionFeeIn(
                amount="85.25", due_on=date(2026, 12, 1),
                receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
            ),
            follow_up_unit_id=unit.id,
        )
        locked = db.get(Organization, admin.organization_id)
        locked.locked_through_date = date.today()
        db.flush()
        with pytest.raises(HTTPException) as error:
            board_api.record_board_decision(
                assoc.id, application.id, payload, db=db, current_user=admin,
            )
        assert error.value.status_code == 409
        assert db.query(HOAARCDecision).count() == 0
        assert db.query(GLTransaction).count() == 0
        assert db.query(WorkOrder).count() == 0
        locked = db.get(Organization, admin.organization_id)
        locked.locked_through_date = None
        db.commit()
        detail = board_api.record_board_decision(
            assoc.id, application.id, payload, db=db, current_user=admin,
        )
        assert detail.status == "APPROVED"
        assert detail.board_decision.notification_status == "SENT"
        assert len(sent) == 1 and sent[0]["to"] == tenant.email
        assert db.query(HOAARCMemberCharge).count() == 1
        fee = db.query(HOAARCMemberCharge).one()
        assert fee.member_user_id == tenant.id
        assert fee.contact_link_id == links[0].id
        assert fee.amount == Decimal("85.25")
        assert fee.due_on == date(2026, 12, 1)
        txn = db.get(GLTransaction, fee.gl_transaction_id)
        assert txn.source_type == "hoa_arc_member_charge"
        assert txn.source_id == application.id
        lines = db.query(GLEntry).filter(GLEntry.transaction_id == txn.id).all()
        assert len(lines) == 2
        assert sum((x.debit for x in lines), Decimal(0)) == Decimal("85.25")
        assert sum((x.credit for x in lines), Decimal(0)) == Decimal("85.25")
        assert {x.gl_account_id for x in lines} == {ar.id, income.id}
        assert all(x.organization_id == admin.organization_id
                   and x.property_id == prop.id for x in lines)
        assert db.query(Charge).count() == db.query(RentInvoice).count() == 0
        work = db.query(WorkOrder).one()
        assert work.unit_id == unit.id and work.tenant_id == tenant.id
        assert detail.board_decision.work_order_id == work.id
        assert detail.board_decision.fee_gl_transaction_id == txn.id
        assert detail.board_decision.member_charge_amount == Decimal("85.25")
        fees = board_api.get_member_fee(
            assoc.id, application.id, Response(),
            property_id=prop.id, db=db, current_user=admin,
        )
        assert fees["member_charge"]["gl_transaction_id"] == txn.id
        with pytest.raises(HTTPException):
            board_api.get_member_fee(
                assoc.id, application.id, Response(),
                property_id=prop.id, db=db, current_user=foreign,
            )
        with pytest.raises(HTTPException) as conflict:
            board_api.record_board_decision(
                assoc.id, application.id, payload, db=db, current_user=admin,
            )
        assert conflict.value.status_code == 409
        assert db.query(GLTransaction).count() == db.query(WorkOrder).count() == 1
        assert len(sent) == 1
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_arc_denial_notification_failure_and_cross_scope_guard(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, links, intake, _ = _seed(db)
        _board_member(db, assoc, prop, admin)
        tenant.is_verified = True
        applicant = db.query(Contact).filter(Contact.id == links[0].contact_id).one()
        applicant.email = tenant.email
        db.commit()
        app = _ready_application(db, assoc, prop, intake, links[0], admin)
        def decide(actor=admin, property_id=prop.id, **changes):
            payload = dict(property_id=property_id, decision="DENIED",
                           decision_note="Board denial recorded")
            payload.update(changes)
            return board_api.record_board_decision(
                assoc.id, app.id, HOAARCDecisionIn(**payload),
                db=db, current_user=actor,
            )
        for actor, prop_id in ((owner, prop.id), (manager, prop.id),
                               (tenant, prop.id), (foreign, prop.id),
                               (admin, other.id), (admin, outside.id)):
            with pytest.raises(HTTPException):
                decide(actor, prop_id)
        admin.is_verified = False
        db.flush()
        with pytest.raises(HTTPException):
            decide()
        admin.is_verified = True
        db.flush()
        with pytest.raises(ValidationError):
            HOAARCDecisionIn(
                property_id=prop.id, decision="APPROVED",
                decision_note="Ok", legal_decision_effective=True,
            )
        with pytest.raises(ValidationError):
            HOAARCDecisionIn(
                property_id=prop.id, decision="DENIED",
                decision_note="Denied", fee={
                    "amount": "25.00", "due_on": date.today(),
                    "receivable_gl_account_id": 1,
                    "income_gl_account_id": 2,
                }, illegally_waive_fines=True,
            )
        with pytest.raises(HTTPException) as exc:
            decide(fee=HOAARCDecisionFeeIn(
                amount="25", due_on=date.today(),
                receivable_gl_account_id=1, income_gl_account_id=2,
            ))
        assert exc.value.status_code == 422
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as exc:
            decide()
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
            SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
        ])
        monkeypatch.setattr(board_api, "send_email", lambda **kw: (_ for _ in ()).throw(RuntimeError("smtp unavailable")))
        result = decide()
        assert result.status == "DENIED"
        assert result.board_decision.notification_status == "FAILED"
        assert db.query(HOAARCDecision).count() == 1
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
        assert db.query(WorkOrder).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()
