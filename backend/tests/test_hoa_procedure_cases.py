"""HOA procedure and violation case workflows stay staff-only and finance-neutral."""
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
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_violation_evidence import HOAViolationEvidence
from app.models.hoa_case_task import HOACaseTask
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft
from app.models.hoa_violation_correspondence import HOAViolationCorrespondenceDraft
from app.models.hoa_violation_notice_delivery import HOAViolationNoticeDelivery
from app.models.hoa_violation_service_record import HOAViolationServiceRecord
from app.models.hoa_violation_fine import HOAViolationFine
from app.models.hoa_violation_fine_payment import HOAViolationFinePayment
from app.models.hoa_violation_fine_appeal import HOAFineAppeal
from app.models.hoa_board import HOABoardSeat
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.routers import hoa_violation_fines as fine_api
from app.routers import hoa_violation_fine_payments as fine_payments
from app.routers import hoa_fine_appeals as appeals_api
from app.routers import hoa_board_portal as board_portal
from app.schemas.hoa_fine_appeal import HOAFineAppealIn, HOAFineAppealDecisionIn
from app.routers import hoa_member_assessments as member_api
from app.schemas.hoa_violation_fine import HOAFineDecisionIn, HOAFinePostIn, HOAFineReverseIn
from app.schemas.hoa_violation_fine_payment import HOAFinePaymentIn, HOAFinePaymentReverseIn
from app.schemas.receipt import ReceiptCreateIn
from app.services.receipt_posting import reverse_receipt, process_nsf_receipt
from app.services.gl_posting import PostingError
from app.routers import hoa_violation_service_records as service_api
from app.schemas.hoa_violation_service_record import HOAServiceRecordIn
from app.models.gl_transaction import GLTransaction
from app.models.hoa_procedure_policy import HOAProcedurePolicy
from app.models.hoa_violation_case import HOAViolationCase
from app.models.hoa_violation_case_event import HOAViolationCaseEvent
from app.models.lease import Lease, RentInvoice
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_observations as observations
from app.routers import hoa_procedure_policies as policies
from app.routers import hoa_violation_cases as cases
from app.routers import hoa_violation_recipients as recipients
from app.routers import hoa_violation_correspondence as correspondence
from app.routers import hoa_violation_notice_delivery as notice_delivery
from app.routers import hoa_arc_board_decisions as arc_board
from app.routers import hoa_board as board_api
from app.core import email as email_service
from app.schemas.hoa_violation_notice_delivery import HOAViolationNoticeSendIn
from app.schemas.hoa_board import HOABoardSeatIn, HOABoardAuthorizationIn
from app.routers import hoa_violation_evidence as case_evidence
from app.routers import hoa_case_tasks as case_tasks
from app.routers import entity_attachments as attachments
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.schemas.hoa_violation_recipient import HOAViolationRecipientIn
from app.routers.hoa_violation_correspondence import CorrespondenceIn
from app.routers.hoa_violation_evidence import EvidenceIn
from app.schemas.hoa_case_task import HOACaseTaskCreateIn, HOACaseTaskTransitionIn
from app.schemas.entity_attachment import EntityAttachmentShareUpdate
from app.schemas.hoa_observation import HOAObservationIn
from app.schemas.hoa_procedure_policy import HOAProcedurePolicyIn
from app.schemas.hoa_violation_case import HOAViolationCaseIn, HOAViolationAdvanceIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="HOA Procedure Org", slug="hoa-procedure-org")
    b = Organization(name="Other Procedure Org", slug="other-procedure-org")
    db.add_all([a, b]); db.flush()
    actors = []
    for org, role, name in (
        (a, UserRole.ADMIN, "admin"), (a, UserRole.OWNER, "owner"),
        (a, UserRole.MANAGER, "manager"), (a, UserRole.TENANT, "tenant"),
        (b, UserRole.ADMIN, "foreign"),
    ):
        u = User(organization_id=org.id, role=role, first_name=name,
                 last_name="Staff", hashed_password="x", is_active=True,
                 email=f"hoa-procedure-{name}@example.test")
        db.add(u); actors.append(u)
    db.flush()
    props = []
    for org, name in ((a, "Assigned"), (a, "Other property"), (b, "Foreign")):
        prop = Property(organization_id=org.id, name=name,
                        address_line1="123 Main", city="Cleveland",
                        state="OH", zip_code="44113", is_active=True)
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=actors[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    assoc = hoa.create_association(HOAAssociationIn(
        name="Staff-only HOA", property_ids=[props[0].id, props[1].id],
    ), db=db, current_user=actors[0])
    obs = observations.create_observation(
        assoc.id,
        HOAObservationIn(
            property_id=props[0].id, summary="Example observation",
            observed_on=date(2026, 9, 1), details="private staff note",
        ),
        db=db, current_user=actors[0],
    )
    return actors, props, assoc, obs


def _profile(property_id, **changes):
    values = dict(
        property_id=property_id, jurisdiction_state="Staff label",
        jurisdiction_locality="Example locality", notice_preparation_days=2,
        cure_preparation_days=5, hearing_request_days=9,
        proposed_fine_cap="25.00", draft_notice_text="Internal example notice DRAFT",
        supporting_evidence_id=None,
    )
    values.update(changes)
    return HOAProcedurePolicyIn(**values)


def _advance(prop, stage, **extra):
    return HOAViolationAdvanceIn(property_id=prop.id, next_stage=stage, **extra)


def _balances(db):
    return (
        db.query(Charge).count(), db.query(GLTransaction).count(),
        db.query(RentInvoice).count(), db.query(Lease).count(),
    )


def test_rule_settings_are_versioned_scoped_and_not_verified_law():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unused, outside), assoc, obs = _seed(db)
        assert policies.get_policy(assoc.id, Response(), assigned.id,
                                   db=db, current_user=manager) is None
        before = _balances(db)
        config = policies.put_policy(
            assoc.id, _profile(assigned.id), db=db, current_user=admin,
        )
        assert config.revision == 1 and config.status == "STAFF_CONFIGURED_UNVERIFIED"
        assert config.issuance_enabled is False
        assert config.cure_preparation_days == 5
        response = Response()
        read = policies.get_policy(assoc.id, response, assigned.id,
                                   db=db, current_user=manager)
        assert read.id == config.id and response.headers["cache-control"] == "no-store"
        revised = policies.put_policy(
            assoc.id, _profile(assigned.id, cure_preparation_days=7),
            db=db, current_user=owner,
        )
        assert revised.id == config.id and revised.revision == 2
        assert revised.cure_preparation_days == 7
        assert _balances(db) == before
        assert db.query(HOAProcedurePolicy).count() == 1
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_procedure_policy",
        ).order_by(AuditLog.id).all()
        assert len(audit) == 2
        assert all("Internal example notice" not in str(a.new_value) for a in audit)
        assert all("Staff label" not in str(a.new_value) for a in audit)
        assert "fine_assessed" not in config.model_dump()
        with pytest.raises(HTTPException) as e:
            _model_for_table("hoa_procedure_policies")
        assert e.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_case_open_notice_cure_hearing_fine_proposal_resolution_closed():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unused, outside), assoc, obs = _seed(db)
        config = policies.put_policy(assoc.id, _profile(assigned.id),
                                     db=db, current_user=admin)
        before = _balances(db)
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(
                property_id=assigned.id, observation_id=obs.id,
            ), db=db, current_user=owner,
        )
        assert case.stage == "OPEN" and case.notice_sent is False
        with pytest.raises(HTTPException) as e:
            cases.create_case(
                assoc.id, HOAViolationCaseIn(
                    property_id=assigned.id, observation_id=obs.id,
                ), db=db, current_user=admin,
            )
        assert e.value.status_code == 409
        case = cases.advance_case(
            assoc.id, case.id,
            _advance(assigned, "NOTICE_DRAFT", action_on=date(2026, 10, 1)),
            db=db, current_user=admin,
        )
        case = cases.advance_case(
            assoc.id, case.id, _advance(assigned, "CURE_TRACKING"),
            db=db, current_user=owner,
        )
        assert case.tentative_cure_on == date(2026, 10, 6)
        assert case.policy_revision == config.revision
        case = cases.advance_case(
            assoc.id, case.id,
            _advance(assigned, "HEARING_PLANNED", action_on=date(2026, 10, 20)),
            db=db, current_user=admin,
        )
        case = cases.advance_case(
            assoc.id, case.id, _advance(assigned, "FINE_PROPOSED", proposed_fine="25.00"),
            db=db, current_user=owner,
        )
        assert case.proposed_fine == Decimal("25.00")
        assert case.fine_assessed is False
        case = cases.advance_case(
            assoc.id, case.id,
            _advance(assigned, "RESOLVED", staff_resolution="Staff follow-up recorded"),
            db=db, current_user=admin,
        )
        case = cases.advance_case(
            assoc.id, case.id, _advance(assigned, "CLOSED"),
            db=db, current_user=admin,
        )
        assert case.stage == "CLOSED" and case.legally_adjudicated is False
        assert len(cases.list_cases(assoc.id, Response(), assigned.id,
                                    db=db, current_user=manager)) == 1
        assert _balances(db) == before
        audits = db.query(AuditLog).filter(AuditLog.entity_type == "hoa_violation_case").all()
        assert len(audits) == 7
        assert all("Staff follow-up recorded" not in str(a.new_value) for a in audits)
        with pytest.raises(HTTPException) as e:
            _model_for_table("hoa_violation_cases")
        assert e.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_invalid_transitions_missing_rule_fields_and_user_supplied_fine():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unused, outside), assoc, obs = _seed(db)
        row = cases.create_case(
            assoc.id, HOAViolationCaseIn(
                property_id=assigned.id, observation_id=obs.id,
            ), db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as e:
            cases.advance_case(
                assoc.id, row.id, _advance(assigned, "FINE_PROPOSED", proposed_fine="50"),
                db=db, current_user=admin,
            )
        assert e.value.status_code == 409
        with pytest.raises(HTTPException) as e:
            cases.advance_case(
                assoc.id, row.id,
                _advance(assigned, "NOTICE_DRAFT", action_on=date(2026, 10, 1)),
                db=db, current_user=admin,
            )
        assert e.value.status_code == 409
        policies.put_policy(assoc.id, _profile(assigned.id,
                             cure_preparation_days=None, proposed_fine_cap="10"),
                            db=db, current_user=admin)
        cases.advance_case(
            assoc.id, row.id,
            _advance(assigned, "NOTICE_DRAFT", action_on=date(2026, 10, 1)),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as e:
            cases.advance_case(
                assoc.id, row.id, _advance(assigned, "CURE_TRACKING"),
                db=db, current_user=admin,
            )
        assert e.value.status_code == 409
        policies.put_policy(assoc.id, _profile(assigned.id,
                             proposed_fine_cap="10"), db=db, current_user=admin)
        cases.advance_case(
            assoc.id, row.id, _advance(assigned, "CURE_TRACKING"),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as e:
            cases.advance_case(
                assoc.id, row.id, _advance(assigned, "FINE_PROPOSED", proposed_fine="11"),
                db=db, current_user=admin,
            )
        assert e.value.status_code == 422
        for data in (
            dict(property_id=assigned.id, next_stage="NOTICE_DRAFT"),
            dict(property_id=assigned.id, next_stage="RESOLVED"),
            dict(property_id=assigned.id, next_stage="FINE_PROPOSED", proposed_fine="0"),
            dict(property_id=assigned.id, next_stage="CURE_TRACKING", proposed_fine="1"),
            dict(property_id=assigned.id, next_stage="CURE_TRACKING", send_notice=True),
        ):
            with pytest.raises(ValidationError):
                HOAViolationAdvanceIn(**data)
        with pytest.raises(ValidationError):
            _profile(assigned.id, fine_schedule="illegal")
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_staff_case_scope_and_feature_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, outside), assoc, obs = _seed(db)
        saved = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=assigned.id, observation_id=obs.id),
            db=db, current_user=admin,
        )
        for actor, prop in (
            (manager, unassigned), (foreign, assigned), (manager, outside),
        ):
            with pytest.raises(HTTPException) as e:
                cases.list_cases(assoc.id, Response(), prop.id, db=db, current_user=actor)
            assert e.value.status_code == 404
            with pytest.raises(HTTPException):
                policies.get_policy(assoc.id, Response(), prop.id,
                                    db=db, current_user=actor)
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                cases.advance_case(
                    assoc.id, saved.id,
                    _advance(assigned, "RESOLVED", staff_resolution="Staff note"),
                    db=db, current_user=actor,
                )
            with pytest.raises(HTTPException):
                policies.put_policy(
                    assoc.id, _profile(assigned.id), db=db, current_user=actor,
                )
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as e:
            cases.list_cases(assoc.id, Response(), assigned.id,
                             db=db, current_user=admin)
        assert e.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as e:
            cases.list_cases(assoc.id, Response(), assigned.id,
                             db=db, current_user=admin)
        assert e.value.status_code == 404
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.close(); engine.dispose()


def test_association_unlink_archives_settings_cases_and_requires_explicit_rerecord():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, outside), assoc, obs = _seed(db)
        settings = policies.put_policy(
            assoc.id, _profile(assigned.id), db=db, current_user=admin,
        )
        record = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=assigned.id, observation_id=obs.id),
            db=db, current_user=admin,
        )
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Staff-only HOA", property_ids=[unassigned.id],
            ), db=db, current_user=owner,
        )
        assert db.get(HOAProcedurePolicy, settings.id).is_active is False
        assert db.get(HOAViolationCase, record.id).is_active is False
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Staff-only HOA", property_ids=[assigned.id, unassigned.id],
            ), db=db, current_user=owner,
        )
        assert policies.get_policy(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        ) is None
        assert cases.list_cases(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        ) == []
        refreshed = policies.put_policy(
            assoc.id, _profile(assigned.id, cure_preparation_days=11),
            db=db, current_user=owner,
        )
        assert refreshed.id == settings.id and refreshed.revision == 2
        assert refreshed.cure_preparation_days == 11
        assert cases.list_cases(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        ) == []
        hoa.archive_association(assoc.id, db=db, current_user=owner)
        assert db.get(HOAProcedurePolicy, settings.id).is_active is False
        assert db.get(HOAViolationCase, record.id).is_active is False
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.close(); engine.dispose()


def test_procedure_reference_must_be_same_scope_private_active_document(monkeypatch):
    from app.models.entity_attachment import EntityAttachment
    from app.models.hoa_governing_evidence import HOAGoverningEvidence
    from app.routers import hoa_governing_evidence as evidence

    monkeypatch.setattr(evidence, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=evidence.ATTACHMENT_FEATURE, allowed=True),
    ])
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, outside), assoc, obs = _seed(db)
        doc = EntityAttachment(
            organization_id=admin.organization_id, entity_type="properties",
            entity_id=assigned.id, storage_key="hoa-policy-sample.pdf",
            original_name="hoa-policy-sample.pdf", content_type="application/pdf",
            size_bytes=10, is_active=True, share_with_tenants=False,
            share_with_owners=False,
        )
        db.add(doc); db.flush()
        reference = HOAGoverningEvidence(
            organization_id=admin.organization_id, association_id=assoc.id,
            property_id=assigned.id, attachment_id=doc.id,
            evidence_type="RULES", is_active=True, created_by_id=admin.id,
        )
        db.add(reference); db.commit()
        policy = policies.put_policy(
            assoc.id, _profile(assigned.id, supporting_evidence_id=reference.id),
            db=db, current_user=owner,
        )
        assert policy.supporting_evidence_id == reference.id
        with pytest.raises(HTTPException) as e:
            policies.put_policy(
                assoc.id, _profile(unassigned.id, supporting_evidence_id=reference.id),
                db=db, current_user=owner,
            )
        assert e.value.status_code == 404
        doc.share_with_owners = True
        db.flush()
        with pytest.raises(HTTPException):
            policies.put_policy(
                assoc.id, _profile(assigned.id, supporting_evidence_id=reference.id),
                db=db, current_user=owner,
            )
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_violation_timeline_records_real_stage_history_without_posting():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, _, _), assoc, obs = _seed(db)
        p = policies.put_policy(assoc.id, _profile(prop.id), db=db, current_user=admin)
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=owner,
        )
        def history(actor=admin, property_id=prop.id):
            return cases.get_case_history(
                assoc.id, case.id, Response(), property_id=property_id,
                db=db, current_user=actor,
            )
        assert len(history()) == 1
        assert history()[0].from_stage is None and history()[0].to_stage == "OPEN"
        cases.advance_case(
            assoc.id, case.id, _advance(prop, "NOTICE_DRAFT", action_on=date(2026, 10, 1)),
            db=db, current_user=admin,
        )
        cases.advance_case(
            assoc.id, case.id, _advance(prop, "CURE_TRACKING"),
            db=db, current_user=owner,
        )
        result = history(manager)
        assert [e.to_stage for e in result] == ["OPEN", "NOTICE_DRAFT", "CURE_TRACKING"]
        assert result[1].from_stage == "OPEN"
        assert result[1].staff_action_on == date(2026, 10, 1)
        assert result[1].policy_revision == p.revision
        assert result[2].tentative_cure_on == date(2026, 10, 6)
        assert all(e.notice_delivered is False and e.fine_posted is False for e in result)
        policies.put_policy(
            assoc.id, _profile(prop.id, cure_preparation_days=15),
            db=db, current_user=admin,
        )
        # Revision and tentative dates are immutable history snapshots.
        older = history()
        assert older[2].policy_revision == 1
        assert older[2].tentative_cure_on == date(2026, 10, 6)
        cases.advance_case(
            assoc.id, case.id,
            _advance(prop, "FINE_PROPOSED", proposed_fine="24.50"),
            db=db, current_user=owner,
        )
        cases.advance_case(
            assoc.id, case.id,
            _advance(prop, "RESOLVED", staff_resolution="Internal follow-up"),
            db=db, current_user=admin,
        )
        cases.advance_case(
            assoc.id, case.id, _advance(prop, "CLOSED"),
            db=db, current_user=admin,
        )
        final = history()
        assert [e.to_stage for e in final][-3:] == [
            "FINE_PROPOSED", "RESOLVED", "CLOSED",
        ]
        assert final[-3].proposed_fine == Decimal("24.50")
        assert final[-2].staff_resolution == "Internal follow-up"
        assert final[-1].from_stage == "RESOLVED"
        assert final[-1].proposed_fine == Decimal("24.50")
        assert len({e.id for e in final}) == 6
        assert db.query(HOAViolationCaseEvent).count() == 6
        response = Response()
        assert len(cases.get_case_history(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=manager,
        )) == 6
        assert response.headers["cache-control"] == "no-store"
        assert _balances(db) == (0, 0, 0, 0)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_violation_case_events")
    finally:
        db.close()
        engine.dispose()


def test_violation_timeline_scope_and_archive_preserve_private_history(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=admin,
        )
        def read(actor, prop_id=prop.id):
            return cases.get_case_history(
                assoc.id, case.id, Response(), property_id=prop_id,
                db=db, current_user=actor,
            )
        for actor, prop_id in (
            (tenant, prop.id), (foreign, prop.id),
            (manager, other.id), (admin, outside.id),
        ):
            with pytest.raises(HTTPException):
                read(actor, prop_id)
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            read(admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as exc:
            read(admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
            SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
        ])
        observations.archive_observation(
            assoc.id, obs.id, prop.id, db=db, current_user=owner,
        )
        with pytest.raises(HTTPException) as exc:
            read(admin)
        assert exc.value.status_code == 404
        assert db.query(HOAViolationCaseEvent).count() == 1
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def _recipient_candidate(db, *, actor, assoc, prop, name, email):
    row = Contact(
        organization_id=actor.organization_id, display_name=name,
        email=email, contact_type="PERSON", is_active=True,
    )
    db.add(row); db.flush()
    return hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(property_id=prop.id, contact_id=row.id),
        db=db, current_user=actor,
    ), row


def test_violation_recipient_requires_matching_verified_login_and_never_sends():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, _, _), assoc, obs = _seed(db)
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=admin,
        )
        link, contact = _recipient_candidate(
            db, actor=admin, assoc=assoc, prop=prop,
            name="Potential member", email=tenant.email,
        )
        response = Response()
        assert recipients.get_case_recipient(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=manager,
        ) is None
        assert response.headers["cache-control"] == "no-store"
        with pytest.raises(HTTPException) as unverified:
            recipients.set_case_recipient(
                assoc.id, case.id,
                HOAViolationRecipientIn(property_id=prop.id, contact_link_id=link.id),
                db=db, current_user=admin,
            )
        assert unverified.value.status_code == 409
        tenant.is_verified = True
        db.flush()
        initial = _balances(db)
        record = recipients.set_case_recipient(
            assoc.id, case.id,
            HOAViolationRecipientIn(property_id=prop.id, contact_link_id=link.id),
            db=db, current_user=admin,
        )
        assert record.contact_name == "Potential member"
        assert record.matched_user_id == tenant.id
        assert record.member_liability_verified is False
        assert record.notice_delivery_enabled is False
        assert record.legal_recipient_certified is False
        assert recipients.get_case_recipient(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        ).matched_user_id == tenant.id
        with pytest.raises(HTTPException) as replay:
            recipients.set_case_recipient(
                assoc.id, case.id,
                HOAViolationRecipientIn(property_id=prop.id, contact_link_id=link.id),
                db=db, current_user=owner,
            )
        assert replay.value.status_code == 409
        # Mutated identity does not permit a stale reference to be used.
        contact.email = owner.email
        db.flush()
        with pytest.raises(HTTPException) as stale:
            recipients.get_case_recipient(
                assoc.id, case.id, Response(), property_id=prop.id,
                db=db, current_user=manager,
            )
        assert stale.value.status_code == 409
        contact.email = tenant.email
        db.flush()
        recipients.clear_case_recipient(
            assoc.id, case.id, property_id=prop.id,
            db=db, current_user=owner,
        )
        assert recipients.get_case_recipient(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        ) is None
        revived = recipients.set_case_recipient(
            assoc.id, case.id,
            HOAViolationRecipientIn(property_id=prop.id, contact_link_id=link.id),
            db=db, current_user=admin,
        )
        assert revived.id == record.id
        assert db.query(HOAViolationRecipientDraft).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_recipient_draft",
        ).count() == 3
        assert _balances(db) == initial
        with pytest.raises(HTTPException) as notes:
            _model_for_table("hoa_violation_recipient_drafts")
        assert notes.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_violation_recipient_scope_permissions_and_closed_cases(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
        tenant.is_verified = True
        link, contact = _recipient_candidate(
            db, actor=admin, assoc=assoc, prop=prop,
            name="Scoped contact", email=tenant.email,
        )
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=admin,
        )
        payload = HOAViolationRecipientIn(property_id=prop.id, contact_link_id=link.id)
        for actor, prop_id in ((manager, prop.id), (tenant, prop.id),
                                (foreign, prop.id), (owner, outside.id)):
            with pytest.raises(HTTPException):
                recipients.set_case_recipient(
                    assoc.id, case.id,
                    HOAViolationRecipientIn(property_id=prop_id, contact_link_id=link.id),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            recipients.set_case_recipient(
                assoc.id, case.id,
                HOAViolationRecipientIn(property_id=other.id, contact_link_id=link.id),
                db=db, current_user=owner,
            )
        monkeypatch.setattr(
            recipients, "permission_allows_user", lambda *a, **kw: False,
        )
        with pytest.raises(HTTPException) as denied:
            recipients.set_case_recipient(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert denied.value.status_code == 403
        monkeypatch.setattr(recipients, "permission_allows_user", lambda *a, **kw: True)
        recipients.set_case_recipient(
            assoc.id, case.id, payload, db=db, current_user=admin,
        )
        for stage, extras in (
            ("RESOLVED", dict(staff_resolution="Staff resolution")),
            ("CLOSED", {}),
        ):
            cases.advance_case(
                assoc.id, case.id, _advance(prop, stage, **extras),
                db=db, current_user=admin,
            )
        with pytest.raises(HTTPException) as closed:
            recipients.clear_case_recipient(
                assoc.id, case.id, property_id=prop.id,
                db=db, current_user=owner,
            )
        assert closed.value.status_code == 409
        with pytest.raises(ValidationError):
            HOAViolationRecipientIn(
                property_id=prop.id, contact_link_id=link.id,
                notice_sent=True,
            )
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()


def _ready_correspondence(db):
    (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
    tenant.is_verified = True
    link, contact = _recipient_candidate(
        db, actor=admin, assoc=assoc, prop=prop,
        name="Private recipient", email=tenant.email,
    )
    policies.put_policy(
        assoc.id, _profile(prop.id), db=db, current_user=admin,
    )
    case = cases.create_case(
        assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
        db=db, current_user=admin,
    )
    cases.advance_case(
        assoc.id, case.id,
        _advance(prop, "NOTICE_DRAFT", action_on=date(2026, 9, 2)),
        db=db, current_user=admin,
    )
    recipients.set_case_recipient(
        assoc.id, case.id,
        HOAViolationRecipientIn(property_id=prop.id, contact_link_id=link.id),
        db=db, current_user=owner,
    )
    return (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, case, link, contact


def test_private_violation_correspondence_snapshots_and_stale_revisions():
    db, engine = _db()
    try:
        users, props, assoc, case, link, contact = _ready_correspondence(db)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        before = _balances(db)
        payload = CorrespondenceIn(
            property_id=prop.id, subject="Internal case preparation",
            body="Internal staff review text; not served.",
        )
        row = correspondence.prepare_correspondence(
            assoc.id, case.id, payload, db=db, current_user=owner,
        )
        assert row.revision == 1 and row.status == "STAFF_DRAFT_NOT_SENT"
        assert row.recipient_reference_current is True
        assert row.policy_revision_current is True
        assert row.case_stage_current is True
        assert row.legally_served is row.fine_assessed is False
        response = Response()
        result = correspondence.get_correspondence(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=manager,
        )
        assert response.headers["cache-control"] == "no-store"
        assert len(result) == 1 and result[0].body == payload.body
        with pytest.raises(HTTPException) as replay:
            correspondence.prepare_correspondence(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert replay.value.status_code == 409

        policies.put_policy(
            assoc.id, _profile(prop.id, cure_preparation_days=8),
            db=db, current_user=admin,
        )
        assert correspondence.get_correspondence(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=owner,
        )[0].policy_revision_current is False

        second = correspondence.prepare_correspondence(
            assoc.id, case.id, payload, db=db, current_user=admin,
        )
        assert second.revision == 2 and second.policy_revision == 2
        assert correspondence.get_correspondence(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )[0].policy_revision == 1

        recipients.clear_case_recipient(
            assoc.id, case.id, property_id=prop.id, db=db, current_user=owner,
        )
        latest = correspondence.get_correspondence(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )
        assert all(not entry.recipient_reference_current for entry in latest)
        with pytest.raises(HTTPException) as missing:
            correspondence.prepare_correspondence(
                assoc.id, case.id,
                CorrespondenceIn(
                    property_id=prop.id, subject="Unmatched",
                    body="Must not accept an inactive reference",
                ),
                db=db, current_user=admin,
            )
        assert missing.value.status_code == 409

        recipients.set_case_recipient(
            assoc.id, case.id,
            HOAViolationRecipientIn(
                property_id=prop.id, contact_link_id=link.id,
            ), db=db, current_user=owner,
        )
        contact.email = foreign.email
        db.flush()
        with pytest.raises(HTTPException):
            correspondence.prepare_correspondence(
                assoc.id, case.id,
                CorrespondenceIn(
                    property_id=prop.id, subject="Incorrect member",
                    body="Must fail when identity is stale",
                ),
                db=db, current_user=admin,
            )
        contact.email = tenant.email
        db.flush()
        cases.advance_case(
            assoc.id, case.id, _advance(prop, "CURE_TRACKING"),
            db=db, current_user=owner,
        )
        assert correspondence.get_correspondence(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )[1].case_stage_current is False
        assert db.query(HOAViolationCorrespondenceDraft).count() == 2
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_correspondence_draft",
        ).count() == 2
        assert _balances(db) == before
        with pytest.raises(HTTPException) as forbidden:
            _model_for_table("hoa_violation_correspondence_drafts")
        assert forbidden.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_private_correspondence_rejects_bad_scope_and_absent_policy(monkeypatch):
    db, engine = _db()
    try:
        users, props, assoc, case, link, contact = _ready_correspondence(db)
        admin, owner, manager, tenant, foreign = users
        prop, other, outside = props
        payload = CorrespondenceIn(
            property_id=prop.id, subject="Internal notice", body="Private preparatory text.",
        )
        for actor, prop_id in (
            (manager, prop.id), (tenant, prop.id),
            (foreign, prop.id), (owner, outside.id),
        ):
            with pytest.raises(HTTPException):
                correspondence.prepare_correspondence(
                    assoc.id, case.id,
                    CorrespondenceIn(
                        property_id=prop_id, subject=payload.subject, body=payload.body,
                    ), db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            correspondence.get_correspondence(
                assoc.id, case.id, Response(), property_id=outside.id,
                db=db, current_user=foreign,
            )
        monkeypatch.setattr(
            recipients, "permission_allows_user", lambda *a, **kw: False,
        )
        with pytest.raises(HTTPException) as denied:
            correspondence.prepare_correspondence(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert denied.value.status_code == 403
        monkeypatch.setattr(
            recipients, "permission_allows_user", lambda *a, **kw: True,
        )
        contact.email = foreign.email
        db.flush()
        with pytest.raises(HTTPException) as stale:
            correspondence.prepare_correspondence(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert stale.value.status_code == 409
        contact.email = tenant.email
        db.flush()
        policy = db.query(HOAProcedurePolicy).filter(
            HOAProcedurePolicy.association_id == assoc.id,
            HOAProcedurePolicy.property_id == prop.id,
        ).one()
        policy.draft_notice_text = None
        db.flush()
        with pytest.raises(HTTPException) as missing:
            correspondence.prepare_correspondence(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert missing.value.status_code == 409
        policy.draft_notice_text = "Staff internal text"
        db.flush()
        cases.advance_case(
            assoc.id, case.id,
            _advance(prop, "RESOLVED", staff_resolution="Case complete internally"),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as terminal:
            correspondence.prepare_correspondence(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert terminal.value.status_code == 409
        for data in (
            {"property_id": prop.id, "subject": "", "body": "valid"},
            {"property_id": prop.id, "subject": "valid", "body": ""},
            {"property_id": prop.id, "subject": "valid", "body": "valid", "send_notice": True},
        ):
            with pytest.raises(ValidationError):
                CorrespondenceIn(**data)
        assert _balances(db) == (0, 0, 0, 0)
        assert db.query(HOAViolationCorrespondenceDraft).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def _private_case_file(db, org_id, prop_id, name, *, shared=False):
    file = EntityAttachment(
        organization_id=org_id, entity_type="properties",
        entity_id=prop_id, storage_key="violation-" + name,
        original_name=name,
        content_type="image/png" if name.endswith(".png") else "application/pdf",
        size_bytes=120, is_active=True,
        share_with_tenants=shared, share_with_owners=False,
    )
    db.add(file); db.flush()
    return file


def test_private_violation_evidence_scope_duplicate_archive_and_finance(monkeypatch):
    monkeypatch.setattr(case_evidence, "_require_attachment_feature", lambda *a, **kw: None)
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=owner,
        )
        private = _private_case_file(db, admin.organization_id, prop.id, "evidence.png")
        public = _private_case_file(db, admin.organization_id, prop.id, "public.pdf", shared=True)
        wrong_property = _private_case_file(db, admin.organization_id, other.id, "other.pdf")
        wrong_org = _private_case_file(db, foreign.organization_id, outside.id, "foreign.pdf")
        initial = _balances(db)
        before = db.query(AuditLog).filter(AuditLog.entity_type == "hoa_violation_evidence").count()
        result = case_evidence.link_case_evidence(
            assoc.id, case.id, EvidenceIn(
                property_id=prop.id, attachment_id=private.id, evidence_type="PHOTO",
            ), db=db, current_user=admin,
        )
        assert result.filename == "evidence.png"
        assert result.private_only is True
        assert result.legal_notice_served is result.legal_violation_proven is False
        response = Response()
        assert [x.attachment_id for x in case_evidence.list_case_evidence(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=manager,
        )] == [private.id]
        assert response.headers["cache-control"] == "no-store"
        for other_file in (public, wrong_property, wrong_org):
            with pytest.raises(HTTPException) as invalid:
                case_evidence.link_case_evidence(
                    assoc.id, case.id, EvidenceIn(
                        property_id=prop.id, attachment_id=other_file.id,
                        evidence_type="DOCUMENT",
                    ), db=db, current_user=owner,
                )
            assert invalid.value.status_code == 404
        with pytest.raises(HTTPException) as replay:
            case_evidence.link_case_evidence(
                assoc.id, case.id, EvidenceIn(
                    property_id=prop.id, attachment_id=private.id,
                    evidence_type="PHOTO",
                ), db=db, current_user=admin,
            )
        assert replay.value.status_code == 409
        monkeypatch.setattr(attachments, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=attachments.ATTACHMENTS_FEATURE_KEY, allowed=True),
        ])
        notes = __import__("app.services.entity_notes", fromlist=["permission_allows_user"])
        monkeypatch.setattr(notes, "permission_allows_user", lambda *a, **kw: True)
        with pytest.raises(HTTPException) as share:
            attachments.update_entity_attachment_sharing(
                private.id, EntityAttachmentShareUpdate(share_with_owners=True),
                db=db, current_user=admin,
            )
        assert share.value.status_code == 403
        case_evidence.archive_case_evidence(
            assoc.id, case.id, result.id, property_id=prop.id,
            db=db, current_user=owner,
        )
        assert case_evidence.list_case_evidence(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        ) == []
        with pytest.raises(HTTPException) as duplicate_after_archive:
            case_evidence.link_case_evidence(
                assoc.id, case.id, EvidenceIn(
                    property_id=prop.id, attachment_id=private.id,
                    evidence_type="PHOTO",
                ), db=db, current_user=admin,
            )
        assert duplicate_after_archive.value.status_code == 409
        assert db.query(HOAViolationEvidence).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_evidence",
        ).count() == before + 2
        assert _balances(db) == initial
        with pytest.raises(HTTPException) as forbidden:
            _model_for_table("hoa_violation_evidence")
        assert forbidden.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_private_violation_evidence_role_isolation_revocation_and_closed_case(monkeypatch):
    monkeypatch.setattr(case_evidence, "_require_attachment_feature", lambda *a, **kw: None)
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=owner,
        )
        private = _private_case_file(db, admin.organization_id, prop.id, "record.pdf")
        for actor, prop_id in (
            (manager, prop.id), (tenant, prop.id),
            (foreign, prop.id), (owner, other.id), (owner, outside.id),
        ):
            with pytest.raises(HTTPException):
                case_evidence.link_case_evidence(
                    assoc.id, case.id, EvidenceIn(
                        property_id=prop_id,
                        attachment_id=private.id, evidence_type="DOCUMENT",
                    ), db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            case_evidence.list_case_evidence(
                assoc.id, case.id, Response(), property_id=outside.id,
                db=db, current_user=foreign,
            )
        monkeypatch.setattr(
            case_evidence, "_require_attachment_feature",
            lambda *a, **kw: (_ for _ in ()).throw(
                HTTPException(status_code=404, detail="No attachment entitlement.")
            ),
        )
        with pytest.raises(HTTPException) as gate:
            case_evidence.link_case_evidence(
                assoc.id, case.id, EvidenceIn(
                    property_id=prop.id, attachment_id=private.id, evidence_type="DOCUMENT",
                ), db=db, current_user=admin,
            )
        assert gate.value.status_code == 404
        monkeypatch.setattr(case_evidence, "_require_attachment_feature", lambda *a, **kw: None)
        created = case_evidence.link_case_evidence(
            assoc.id, case.id, EvidenceIn(
                property_id=prop.id, attachment_id=private.id, evidence_type="DOCUMENT",
            ), db=db, current_user=admin,
        )
        cases.advance_case(
            assoc.id, case.id,
            _advance(prop, "RESOLVED", staff_resolution="Case resolved"),
            db=db, current_user=admin,
        )
        cases.advance_case(
            assoc.id, case.id, _advance(prop, "CLOSED"),
            db=db, current_user=owner,
        )
        with pytest.raises(HTTPException) as closed:
            case_evidence.archive_case_evidence(
                assoc.id, case.id, created.id, property_id=prop.id,
                db=db, current_user=owner,
            )
        assert closed.value.status_code == 409
        assert [x.attachment_id for x in case_evidence.list_case_evidence(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )] == [private.id]
        with pytest.raises(ValidationError):
            EvidenceIn(
                property_id=prop.id, attachment_id=private.id,
                evidence_type="DOCUMENT", share_with_tenants=True,
            )
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()


def _staff_task(prop, assigned, request_key="case-followup-0001", **changes):
    values = dict(
        property_id=prop.id, request_key=request_key,
        title="Inspect the reported condition",
        details="Private staff assignment.",
        kind="INSPECTION", assigned_user_id=assigned.id,
        due_on=date(2026, 10, 2),
    )
    values.update(changes)
    return HOACaseTaskCreateIn(**values)


def _task_step(prop, next_status, expected_version, note=None):
    return HOACaseTaskTransitionIn(
        property_id=prop.id, next_status=next_status,
        expected_version=expected_version, action_note=note,
    )


def test_case_tasks_verified_assignment_idempotency_and_manager_completion():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
        admin.is_verified = True
        manager.is_verified = True
        db.flush()
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=owner,
        )
        before = _balances(db)
        response = Response()
        assignees = case_tasks.list_assignees(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=manager,
        )
        assert response.headers["cache-control"] == "no-store"
        assert {x.id for x in assignees} == {admin.id, manager.id}
        payload = _staff_task(prop, manager)
        created = case_tasks.create_task(
            assoc.id, case.id, payload, db=db, current_user=admin,
        )
        assert created.status == "OPEN" and created.version == 1
        assert created.internal_only and not created.notice_issued
        repeated = case_tasks.create_task(
            assoc.id, case.id, payload, db=db, current_user=owner,
        )
        assert repeated.id == created.id
        assert db.query(HOACaseTask).count() == 1
        assert len(case_tasks.list_tasks(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )) == 1
        with pytest.raises(HTTPException) as wrong_key:
            case_tasks.create_task(
                assoc.id, case.id,
                _staff_task(prop, manager, title="Different task"),
                db=db, current_user=admin,
            )
        assert wrong_key.value.status_code == 409
        assert case_tasks.transition_task(
            assoc.id, case.id, created.id,
            _task_step(prop, "IN_PROGRESS", 1),
            db=db, current_user=manager,
        ).version == 2
        with pytest.raises(HTTPException) as stale:
            case_tasks.transition_task(
                assoc.id, case.id, created.id,
                _task_step(prop, "DONE", 1, "Checked"),
                db=db, current_user=manager,
            )
        assert stale.value.status_code == 409
        with pytest.raises(HTTPException) as note:
            case_tasks.transition_task(
                assoc.id, case.id, created.id,
                _task_step(prop, "DONE", 2),
                db=db, current_user=manager,
            )
        assert note.value.status_code == 422
        complete = case_tasks.transition_task(
            assoc.id, case.id, created.id,
            _task_step(prop, "DONE", 2, "Staff inspection completed"),
            db=db, current_user=manager,
        )
        assert complete.status == "DONE" and complete.version == 3
        assert complete.completed_at is not None
        assert complete.result_note == "Staff inspection completed"
        with pytest.raises(HTTPException) as replay:
            case_tasks.transition_task(
                assoc.id, case.id, created.id,
                _task_step(prop, "DONE", 3, "Second completion"),
                db=db, current_user=admin,
            )
        assert replay.value.status_code == 409
        events = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_case_task",
        ).order_by(AuditLog.id).all()
        assert len(events) == 3
        assert all("Staff inspection completed" not in (ev.new_value or "") for ev in events)
        assert _balances(db) == before
        with pytest.raises(HTTPException) as generic:
            _model_for_table("hoa_case_tasks")
        assert generic.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_case_tasks_property_auth_revocation_and_close_requires_clearance():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, obs = _seed(db)
        admin.is_verified = True
        manager.is_verified = True
        db.flush()
        case = cases.create_case(
            assoc.id, HOAViolationCaseIn(property_id=prop.id, observation_id=obs.id),
            db=db, current_user=owner,
        )
        before = _balances(db)
        task_payload = _staff_task(prop, manager, request_key="case-followup-0002")
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                case_tasks.create_task(
                    assoc.id, case.id, task_payload, db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            case_tasks.create_task(
                assoc.id, case.id, _staff_task(other, admin),
                db=db, current_user=owner,
            )
        with pytest.raises(HTTPException):
            case_tasks.create_task(
                assoc.id, case.id, _staff_task(prop, tenant),
                db=db, current_user=owner,
            )
        manager.is_verified = False
        db.flush()
        with pytest.raises(HTTPException) as invalid_assignee:
            case_tasks.create_task(
                assoc.id, case.id, task_payload, db=db, current_user=owner,
            )
        assert invalid_assignee.value.status_code == 404
        manager.is_verified = True
        db.flush()
        created = case_tasks.create_task(
            assoc.id, case.id, task_payload, db=db, current_user=admin,
        )
        cases.advance_case(
            assoc.id, case.id, _advance(prop, "RESOLVED", staff_resolution="Review resolved"),
            db=db, current_user=owner,
        )
        with pytest.raises(HTTPException) as incomplete:
            cases.advance_case(
                assoc.id, case.id, _advance(prop, "CLOSED"),
                db=db, current_user=owner,
            )
        assert incomplete.value.status_code == 409
        with pytest.raises(HTTPException) as stranger:
            case_tasks.transition_task(
                assoc.id, case.id, created.id,
                _task_step(prop, "CANCELLED", 1),
                db=db, current_user=foreign,
            )
        assert stranger.value.status_code in {403, 404}
        with pytest.raises(HTTPException) as unauthorized:
            case_tasks.transition_task(
                assoc.id, case.id, created.id,
                _task_step(prop, "CANCELLED", 1),
                db=db, current_user=manager,
            )
        assert unauthorized.value.status_code == 403
        cancelled = case_tasks.transition_task(
            assoc.id, case.id, created.id,
            _task_step(prop, "CANCELLED", 1, "No longer required"),
            db=db, current_user=owner,
        )
        assert cancelled.status == "CANCELLED" and cancelled.version == 2
        closed = cases.advance_case(
            assoc.id, case.id, _advance(prop, "CLOSED"),
            db=db, current_user=owner,
        )
        assert closed.stage == "CLOSED"
        assert len(case_tasks.list_tasks(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )) == 1
        with pytest.raises(HTTPException) as terminal:
            case_tasks.transition_task(
                assoc.id, case.id, created.id,
                _task_step(prop, "IN_PROGRESS", 2),
                db=db, current_user=owner,
            )
        assert terminal.value.status_code == 409
        with pytest.raises(HTTPException) as terminal_create:
            case_tasks.create_task(
                assoc.id, case.id, _staff_task(prop, admin, request_key="case-followup-0003"),
                db=db, current_user=admin,
            )
        assert terminal_create.value.status_code == 409
        assert _balances(db) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def _notice_board(db, monkeypatch):
    users, props, assoc, case, link, contact = _ready_correspondence(db)
    admin, owner, manager, tenant, foreign = users
    prop = props[0]
    admin.is_verified = True
    db.flush()
    board_link, _ = _recipient_candidate(
        db, actor=admin, assoc=assoc, prop=prop,
        name="Association board login", email=admin.email,
    )
    seat = board_api.record_board_seat(
        assoc.id,
        HOABoardSeatIn(
            property_id=prop.id, contact_link_id=board_link.id,
            proposed_role="CHAIR", staff_voting_eligible=True,
        ), db=db, current_user=admin,
    )
    board_api.authorize_board_seat(
        assoc.id, seat.id, HOABoardAuthorizationIn(
            property_id=prop.id, user_id=admin.id, can_record_offline=True,
        ), db=db, current_user=admin,
    )
    monkeypatch.setattr(arc_board, "resolve_customer_features",
                        lambda *a, **kw: [
                            SimpleNamespace(
                                key=k, release_allowed=True,
                                entitlement_allowed=True, org_config_allowed=True,
                            ) for k in arc_board.HOA_GATES
                        ])
    original = correspondence.prepare_correspondence(
        assoc.id, case.id,
        CorrespondenceIn(
            property_id=prop.id, subject="Association case email",
            body="Association-authored synthetic correspondence",
        ), db=db, current_user=admin,
    )
    payload = HOAViolationNoticeSendIn(
        property_id=prop.id, correspondence_revision=original.revision,
        policy_revision=original.policy_revision,
        request_key="notice-email-request-0001",
    )
    return users, props, assoc, case, original, seat, payload


def test_authorized_case_email_exact_revision_idempotency_and_no_finance(monkeypatch):
    db, engine = _db()
    try:
        users, props, assoc, case, draft, seat, payload = _notice_board(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        before = _balances(db)
        sent = []
        monkeypatch.setattr(email_service, "send_email", lambda **kw: sent.append(kw))
        monkeypatch.setattr(email_service, "settings", SimpleNamespace(EMAIL_MODE="smtp"))
        delivery = notice_delivery.send_notice_email(
            assoc.id, case.id, draft.id, payload, db=db, current_user=admin,
        )
        assert delivery.status == "SMTP_ACCEPTED" and delivery.attempt_count == 1
        assert delivery.smtp_accepted_at is not None
        assert delivery.legally_served is False and delivery.fine_assessed is False
        assert delivery.smtp_is_proof_of_receipt is False
        assert len(sent) == 1 and sent[0]["to"] == tenant.email.lower()
        assert sent[0]["subject"] == "Association case email"
        assert sent[0]["body"] == "Association-authored synthetic correspondence"
        assert sent[0]["organization_id"] == admin.organization_id
        again = notice_delivery.send_notice_email(
            assoc.id, case.id, draft.id, payload, db=db, current_user=admin,
        )
        assert again.id == delivery.id and len(sent) == 1
        with pytest.raises(HTTPException) as collision:
            notice_delivery.send_notice_email(
                assoc.id, case.id, draft.id,
                HOAViolationNoticeSendIn(
                    property_id=prop.id, correspondence_revision=2,
                    policy_revision=1, request_key=payload.request_key,
                ), db=db, current_user=admin,
            )
        assert collision.value.status_code == 409
        with pytest.raises(HTTPException) as duplicate:
            notice_delivery.send_notice_email(
                assoc.id, case.id, draft.id,
                HOAViolationNoticeSendIn(
                    property_id=prop.id, correspondence_revision=1,
                    policy_revision=1, request_key="notice-email-request-0002",
                ), db=db, current_user=admin,
            )
        assert duplicate.value.status_code == 409
        rows = notice_delivery.list_notice_emails(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )
        assert len(rows) == 1 and rows[0].id == delivery.id
        assert len(sent) == 1
        assert notice_delivery.retry_notice_email(
            assoc.id, case.id, delivery.id, prop.id, db=db, current_user=admin,
        ).status == "SMTP_ACCEPTED"
        assert len(sent) == 1
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_notice_delivery",
        ).all()
        assert len(audit) == 3
        assert all("Association-authored synthetic correspondence" not in str(ev.new_value) for ev in audit)
        assert all(tenant.email not in str(ev.new_value) for ev in audit)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_violation_notice_deliveries")
        assert _balances(db) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_case_email_requires_current_board_policy_recipient_and_stage(monkeypatch):
    db, engine = _db()
    try:
        users, props, assoc, case, draft, seat, payload = _notice_board(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop, other, outside = props
        before = _balances(db)
        sent = []
        monkeypatch.setattr(email_service, "send_email", lambda **kw: sent.append(kw))
        monkeypatch.setattr(email_service, "settings", SimpleNamespace(EMAIL_MODE="console"))
        for actor, prop_id in (
            (owner, prop.id), (manager, prop.id),
            (tenant, prop.id), (foreign, prop.id),
            (admin, other.id), (admin, outside.id),
        ):
            with pytest.raises(HTTPException):
                notice_delivery.send_notice_email(
                    assoc.id, case.id, draft.id,
                    payload.model_copy(update={"property_id": prop_id}),
                    db=db, current_user=actor,
                )
        policies.put_policy(
            assoc.id, _profile(prop.id, cure_preparation_days=None),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as stale:
            notice_delivery.send_notice_email(
                assoc.id, case.id, draft.id, payload, db=db, current_user=admin,
            )
        assert stale.value.status_code == 409
        fresh = correspondence.prepare_correspondence(
            assoc.id, case.id,
            CorrespondenceIn(
                property_id=prop.id, subject="Updated revision",
                body="Same privacy protections after a policy change",
            ), db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as missing_cure:
            notice_delivery.send_notice_email(
                assoc.id, case.id, fresh.id,
                payload.model_copy(update={
                    "correspondence_revision": fresh.revision,
                    "policy_revision": fresh.policy_revision,
                }), db=db, current_user=admin,
            )
        assert missing_cure.value.status_code == 409
        policies.put_policy(assoc.id, _profile(prop.id), db=db, current_user=admin)
        recipient = recipients.get_case_recipient(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=admin,
        )
        recipients.clear_case_recipient(
            assoc.id, case.id, property_id=prop.id,
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException):
            notice_delivery.send_notice_email(
                assoc.id, case.id, fresh.id,
                payload.model_copy(update={
                    "correspondence_revision": fresh.revision,
                    "policy_revision": fresh.policy_revision,
                }), db=db, current_user=admin,
            )
        assert db.query(HOAViolationNoticeDelivery).count() == 0
        assert sent == []
        assert _balances(db) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_case_email_failure_retry_and_current_scope_revocation(monkeypatch):
    db, engine = _db()
    try:
        users, props, assoc, case, draft, seat, payload = _notice_board(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        before = _balances(db)
        attempts = []
        def transport(**kw):
            attempts.append(kw["to"])
            if len(attempts) == 1:
                raise RuntimeError("Synthetic email transport failure")
        monkeypatch.setattr(email_service, "send_email", transport)
        monkeypatch.setattr(email_service, "settings", SimpleNamespace(EMAIL_MODE="smtp"))
        failed = notice_delivery.send_notice_email(
            assoc.id, case.id, draft.id, payload, db=db, current_user=admin,
        )
        assert failed.status == "FAILED" and failed.attempt_count == 1
        assert len(attempts) == 1
        admin.is_verified = False
        db.flush()
        with pytest.raises(HTTPException):
            notice_delivery.retry_notice_email(
                assoc.id, case.id, failed.id, prop.id, db=db, current_user=admin,
            )
        admin.is_verified = True
        db.flush()
        tenant.is_verified = False
        db.flush()
        with pytest.raises(HTTPException):
            notice_delivery.retry_notice_email(
                assoc.id, case.id, failed.id, prop.id, db=db, current_user=admin,
            )
        tenant.is_verified = True
        db.flush()
        succeeded = notice_delivery.retry_notice_email(
            assoc.id, case.id, failed.id, prop.id, db=db, current_user=admin,
        )
        assert succeeded.status == "SMTP_ACCEPTED" and succeeded.attempt_count == 2
        assert len(attempts) == 2 and _balances(db) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def _service_proof(db, users, prop, assoc, case):
    admin = users[0]
    proof = EntityAttachment(
        organization_id=admin.organization_id,
        entity_type="properties", entity_id=prop.id,
        storage_key="synthetic-hoa-service-proof-" + str(case.id) + ".pdf",
        original_name="synthetic-hoa-service-proof.pdf",
        content_type="application/pdf", size_bytes=12,
        is_active=True, share_with_tenants=False, share_with_owners=False,
    )
    db.add(proof); db.flush()
    db.add(HOAViolationEvidence(
        organization_id=admin.organization_id,
        association_id=assoc.id, property_id=prop.id,
        case_id=case.id, attachment_id=proof.id,
        evidence_type="DOCUMENT", is_active=True,
        recorded_by_id=admin.id,
    ))
    db.commit()
    return proof


def _service_payload(prop, draft, tenant, proof, **changes):
    values = dict(
        property_id=prop.id, correspondence_id=draft.id,
        correspondence_revision=draft.revision,
        policy_revision=draft.policy_revision,
        member_user_id=tenant.id, proof_attachment_id=proof.id,
        delivery_method="PERSONAL", served_on=date(2026, 9, 3),
        request_key="hoa-evidenced-service-0001",
    )
    values.update(changes)
    return HOAServiceRecordIn(**values)


def test_board_records_real_service_evidence_without_notice_inference_or_finance(monkeypatch):
    db, engine = _db()
    try:
        users, props, assoc, case, draft, seat, payload = _notice_board(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        proof = _service_proof(db, users, prop, assoc, case)
        before = _balances(db)
        response = Response()
        assert service_api.get_service_record(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=manager,
        ) is None
        assert response.headers["cache-control"] == "no-store"
        request = _service_payload(prop, draft, tenant, proof)
        result = service_api.record_service(
            assoc.id, case.id, request, db=db, current_user=admin,
        )
        assert result.board_seat_id == seat.id
        assert result.member_user_id == tenant.id
        assert result.correspondence_revision == draft.revision
        assert result.cure_earliest_on == date(2026, 9, 8)
        assert result.hearing_request_earliest_on == date(2026, 9, 12)
        assert result.platform_certifies_service is False
        assert service_api.record_service(
            assoc.id, case.id, request, db=db, current_user=admin,
        ).id == result.id
        with pytest.raises(HTTPException) as key:
            service_api.record_service(
                assoc.id, case.id,
                _service_payload(prop, draft, tenant, proof, delivery_method="OTHER"),
                db=db, current_user=admin,
            )
        assert key.value.status_code == 409
        with pytest.raises(HTTPException) as second:
            service_api.record_service(
                assoc.id, case.id,
                _service_payload(prop, draft, tenant, proof,
                                 request_key="hoa-evidenced-service-0002"),
                db=db, current_user=admin,
            )
        assert second.value.status_code == 409
        visible = service_api.get_service_record(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )
        assert visible.id == result.id
        assert _balances(db) == before
        assert db.query(HOAViolationServiceRecord).count() == 1
        evidence_link = db.query(HOAViolationEvidence).filter(
            HOAViolationEvidence.case_id == case.id,
            HOAViolationEvidence.attachment_id == proof.id,
        ).one()
        monkeypatch.setattr(attachments, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(
                key=attachments.ATTACHMENTS_FEATURE_KEY, allowed=True,
            )])
        monkeypatch.setattr(attachments, "resolve_note_target",
                            lambda *a, **kw: None)
        with pytest.raises(HTTPException) as proof_delete:
            attachments.delete_entity_attachment(
                proof.id, db=db, current_user=admin,
            )
        assert proof_delete.value.status_code == 409
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_service_record",
        ).all()
        assert len(audit) == 1
        assert "synthetic-hoa-service-proof" not in str(audit[0].new_value)
        assert "Association case email" not in str(audit[0].new_value)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_violation_service_records")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_service_record_denies_stale_policy_recipient_scope_and_nonboard(monkeypatch):
    db, engine = _db()
    try:
        users, props, assoc, case, draft, seat, payload = _notice_board(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop, other, outside = props
        proof = _service_proof(db, users, prop, assoc, case)
        request = _service_payload(prop, draft, tenant, proof)
        for actor, prop_id in (
            (owner, prop.id), (manager, prop.id), (tenant, prop.id),
            (foreign, prop.id), (admin, other.id), (admin, outside.id),
        ):
            with pytest.raises(HTTPException):
                service_api.record_service(
                    assoc.id, case.id,
                    request.model_copy(update={"property_id": prop_id}),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            service_api.record_service(
                assoc.id, case.id,
                request.model_copy(update={"member_user_id": admin.id}),
                db=db, current_user=admin,
            )
        with pytest.raises(HTTPException):
            service_api.record_service(
                assoc.id, case.id,
                request.model_copy(update={"served_on": date(2026, 9, 1)}),
                db=db, current_user=admin,
            )
        tenant.is_verified = False
        db.flush()
        with pytest.raises(HTTPException):
            service_api.record_service(
                assoc.id, case.id, request, db=db, current_user=admin,
            )
        tenant.is_verified = True
        db.flush()
        policies.put_policy(
            assoc.id, _profile(prop.id, cure_preparation_days=15),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException):
            service_api.record_service(
                assoc.id, case.id, request, db=db, current_user=admin,
            )
        assert db.query(HOAViolationServiceRecord).count() == 0
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()


def _record_served_fine_case(db, monkeypatch):
    users, props, assoc, case, draft, seat, _ = _notice_board(db, monkeypatch)
    admin, owner, manager, tenant, foreign = users
    prop = props[0]
    proof = _service_proof(db, users, prop, assoc, case)
    service_api.record_service(
        assoc.id, case.id, _service_payload(prop, draft, tenant, proof),
        db=db, current_user=admin,
    )
    cases.advance_case(
        assoc.id, case.id, _advance(prop, "CURE_TRACKING"),
        db=db, current_user=admin,
    )
    cases.advance_case(
        assoc.id, case.id, _advance(prop, "FINE_PROPOSED", proposed_fine="25.00"),
        db=db, current_user=owner,
    )
    return users, props, assoc, case, draft, seat, proof


def _fine_decision(prop, member, **changes):
    values = dict(
        property_id=prop.id, decision="APPROVED",
        amount="25.00", member_user_id=member.id,
        decision_note="The association board adopted the fine after its configured procedure.",
        hearing_disposition="NO_REQUEST_RECORDED",
        request_key="hoa-fine-decision-00001",
    )
    values.update(changes)
    return HOAFineDecisionIn(**values)


def test_board_adopts_fine_and_accountant_posts_and_reverses_central_gl(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        initial = _balances(db)
        response = Response()
        assert fine_api.get_fine(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=admin,
        ) is None
        assert response.headers["cache-control"] == "no-store"
        values = _fine_decision(prop, tenant)
        fine = fine_api.decide_fine(
            assoc.id, case.id, values, db=db, current_user=admin,
        )
        assert fine.decision == "APPROVED" and fine.status == "APPROVED"
        assert fine.member_user_id == tenant.id and fine.amount == Decimal("25.00")
        assert fine.direct_board_decision and fine.tenant_charge_inferred is False
        assert fine.gl_transaction_id is None and fine.board_seat_id == seat.id
        assert fine_api.decide_fine(
            assoc.id, case.id, values, db=db, current_user=admin,
        ).id == fine.id
        with pytest.raises(HTTPException) as collision:
            fine_api.decide_fine(
                assoc.id, case.id,
                _fine_decision(prop, tenant, amount="20.00"),
                db=db, current_user=admin,
            )
        assert collision.value.status_code == 409
        assert _balances(db) == initial
        ar = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-FINE-AR",
            name="Member fine receivable", account_type="ASSET", is_active=True,
        )
        income = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-FINE-INCOME",
            name="HOA fine income", account_type="INCOME", is_active=True,
        )
        db.add_all([ar, income]); db.commit()
        terms = HOAFinePostIn(
            property_id=prop.id, posting_on=date.today(),
            receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
        )
        with pytest.raises(HTTPException):
            fine_api.post_fine(
                assoc.id, case.id,
                terms.model_copy(update={"income_gl_account_id": ar.id}),
                db=db, current_user=admin,
            )
        assert db.query(GLTransaction).count() == 0
        posted = fine_api.post_fine(
            assoc.id, case.id, terms, db=db, current_user=owner,
        )
        assert posted.status == "POSTED" and posted.gl_transaction_id is not None
        entries = db.query(GLEntry).filter(
            GLEntry.transaction_id == posted.gl_transaction_id,
        ).all()
        assert len(entries) == 2
        assert any(e.gl_account_id == ar.id and e.debit == Decimal("25.00") for e in entries)
        assert any(e.gl_account_id == income.id and e.credit == Decimal("25.00") for e in entries)
        again = fine_api.post_fine(
            assoc.id, case.id, terms, db=db, current_user=admin,
        )
        assert again.gl_transaction_id == posted.gl_transaction_id
        assert db.query(GLTransaction).count() == 1
        with pytest.raises(HTTPException) as duplicate:
            fine_api.post_fine(
                assoc.id, case.id,
                terms.model_copy(update={"posting_on": date(2026, 9, 20)}),
                db=db, current_user=admin,
            )
        assert duplicate.value.status_code == 409
        reversed_fine = fine_api.reverse_fine(
            assoc.id, case.id,
            HOAFineReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Board-authorized reversal correction",
            ), db=db, current_user=admin,
        )
        assert reversed_fine.status == "REVERSED"
        assert reversed_fine.reversal_transaction_id is not None
        assert db.query(GLTransaction).count() == 2
        assert db.get(GLTransaction, posted.gl_transaction_id).is_reversed
        with pytest.raises(HTTPException):
            fine_api.reverse_fine(
                assoc.id, case.id,
                HOAFineReverseIn(
                    property_id=prop.id, reversal_on=date.today(),
                    reason="Double reversal",
                ), db=db, current_user=owner,
            )
        assert db.query(Charge).count() == db.query(RentInvoice).count() == 0
        assert db.query(HOAViolationFine).count() == 1
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_fine",
        ).order_by(AuditLog.id).all()
        assert len(audit) == 3
        assert all(values.decision_note not in str(a.new_value) for a in audit)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_violation_fines")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_fine_board_auth_service_policy_hearing_and_member_revocation(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop, other, outside = props
        before = _balances(db)
        payload = _fine_decision(prop, tenant)
        for actor, property_id in (
            (owner, prop.id), (manager, prop.id), (tenant, prop.id),
            (foreign, prop.id), (admin, other.id), (admin, outside.id),
        ):
            with pytest.raises(HTTPException):
                fine_api.decide_fine(
                    assoc.id, case.id,
                    payload.model_copy(update={"property_id": property_id}),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as stranger:
            fine_api.decide_fine(
                assoc.id, case.id,
                _fine_decision(prop, admin), db=db, current_user=admin,
            )
        assert stranger.value.status_code == 409
        tenant.is_verified = False; db.flush()
        with pytest.raises(HTTPException):
            fine_api.decide_fine(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        tenant.is_verified = True; db.flush()
        with pytest.raises(ValidationError):
            _fine_decision(prop, tenant, amount="-1.00")
        with pytest.raises(ValidationError):
            _fine_decision(prop, tenant, hearing_disposition="HEARING_HELD")
        with pytest.raises(ValidationError):
            _fine_decision(prop, tenant, decision="DENIED")
        with pytest.raises(HTTPException) as above_cap:
            fine_api.decide_fine(
                assoc.id, case.id,
                _fine_decision(prop, tenant, amount="26.00"),
                db=db, current_user=admin,
            )
        assert above_cap.value.status_code == 422
        with pytest.raises(HTTPException) as missing_hearing:
            fine_api.decide_fine(
                assoc.id, case.id,
                _fine_decision(
                    prop, tenant, hearing_disposition="HEARING_HELD",
                    hearing_held_on=date.today(),
                    hearing_record_attachment_id=987654321,
                ), db=db, current_user=admin,
            )
        assert missing_hearing.value.status_code == 409
        denial = fine_api.decide_fine(
            assoc.id, case.id,
            _fine_decision(
                prop, tenant, decision="DENIED", amount=None,
                member_user_id=None, request_key="hoa-fine-denial-00001",
            ), db=db, current_user=admin,
        )
        assert denial.status == "DENIED" and denial.amount is None
        with pytest.raises(HTTPException):
            fine_api.post_fine(
                assoc.id, case.id,
                HOAFinePostIn(
                    property_id=prop.id, posting_on=date.today(),
                    receivable_gl_account_id=1, income_gl_account_id=2,
                ), db=db, current_user=admin,
            )
        assert _balances(db) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_fine_refuses_stale_service_or_policy_and_locked_period(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        fine_api.decide_fine(
            assoc.id, case.id, _fine_decision(prop, tenant),
            db=db, current_user=admin,
        )
        ar = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-FINE-LOCK-AR",
            name="Fine locked AR", account_type="ASSET", is_active=True,
        )
        income = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-FINE-LOCK-INCOME",
            name="Fine locked income", account_type="INCOME", is_active=True,
        )
        db.add_all([ar, income]); db.commit()
        org = db.get(Organization, admin.organization_id)
        org.locked_through_date = date.today(); db.flush()
        with pytest.raises(HTTPException) as locked:
            fine_api.post_fine(
                assoc.id, case.id,
                HOAFinePostIn(
                    property_id=prop.id, posting_on=date.today(),
                    receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
                ), db=db, current_user=admin,
            )
        assert locked.value.status_code == 409
        assert db.query(GLTransaction).count() == 0
        org.locked_through_date = None; db.flush()
        policies.put_policy(
            assoc.id, _profile(prop.id, proposed_fine_cap="20.00"),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as stale:
            fine_api.post_fine(
                assoc.id, case.id,
                HOAFinePostIn(
                    property_id=prop.id, posting_on=date.today(),
                    receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
                ), db=db, current_user=admin,
            )
        assert stale.value.status_code == 409
        assert db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_recorded_hearing_private_proof_is_retained_and_staff_cannot_rewrite_board_outcome(monkeypatch):
    db, engine = _db()
    try:
        # This fixture tests evidence retention, not document feature rollout.
        monkeypatch.setattr(case_evidence, "_require_attachment_feature", lambda *a, **kw: None)
        users, props, assoc, case, draft, seat, service_proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        hearing = EntityAttachment(
            organization_id=admin.organization_id,
            entity_type="properties", entity_id=prop.id,
            storage_key="synthetic-private-hearing-proof.pdf",
            original_name="synthetic-private-hearing-proof.pdf",
            content_type="application/pdf", size_bytes=10,
            is_active=True, share_with_tenants=False, share_with_owners=False,
        )
        db.add(hearing); db.flush()
        link = HOAViolationEvidence(
            organization_id=admin.organization_id,
            association_id=assoc.id, property_id=prop.id,
            case_id=case.id, attachment_id=hearing.id,
            evidence_type="DOCUMENT", is_active=True,
            recorded_by_id=admin.id,
        )
        db.add(link); db.commit()
        approved = fine_api.decide_fine(
            assoc.id, case.id,
            _fine_decision(
                prop, tenant, hearing_disposition="HEARING_HELD",
                hearing_held_on=date.today(),
                hearing_record_attachment_id=hearing.id,
            ), db=db, current_user=admin,
        )
        assert approved.status == "APPROVED"
        assert approved.hearing_record_attachment_id == hearing.id
        with pytest.raises(HTTPException) as changed:
            cases.advance_case(
                assoc.id, case.id,
                _advance(prop, "HEARING_PLANNED", action_on=date.today()),
                db=db, current_user=owner,
            )
        assert changed.value.status_code == 409
        monkeypatch.setattr(attachments, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(
                key=attachments.ATTACHMENTS_FEATURE_KEY, allowed=True,
            )])
        monkeypatch.setattr(attachments, "resolve_note_target", lambda *a, **kw: None)
        with pytest.raises(HTTPException) as removed:
            case_evidence.archive_case_evidence(
                assoc.id, case.id, link.id, property_id=prop.id,
                db=db, current_user=owner,
            )
        assert removed.value.status_code == 409
        with pytest.raises(HTTPException) as deleted:
            attachments.delete_entity_attachment(
                hearing.id, db=db, current_user=admin,
            )
        assert deleted.value.status_code == 409
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()

def _fine_receipt(prop, member, cash, *, key="hoa-fine-receipt-00001",
                  amount="10.00", reference="FINE-CHECK-100", **extra):
    values = dict(
        property_id=prop.id, member_user_id=member.id,
        cash_gl_account_id=cash.id, received_on=date.today(),
        amount=amount, payment_reference=reference, idempotency_key=key,
    )
    values.update(extra)
    return HOAFinePaymentIn(**values)


def _fine_receipt_reversal(prop, **extra):
    values = dict(
        property_id=prop.id, reversal_on=date.today(),
        reason="Correct independently recorded fine funds",
    )
    values.update(extra)
    return HOAFinePaymentReverseIn(**values)


def test_actual_fine_receipt_partial_full_reversal_and_paid_fine_guard(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        fine_api.decide_fine(
            assoc.id, case.id, _fine_decision(prop, tenant),
            db=db, current_user=admin,
        )
        ar = GLAccount(
            organization_id=admin.organization_id, gl_number="FINE-PAY-AR",
            name="Fine receivable", account_type="ASSET", is_active=True,
        )
        income = GLAccount(
            organization_id=admin.organization_id, gl_number="FINE-PAY-INCOME",
            name="Fine income", account_type="INCOME", is_active=True,
        )
        cash = GLAccount(
            organization_id=admin.organization_id, gl_number="FINE-PAY-CASH",
            name="Actually received cash", account_type="ASSET",
            include_on_cash_flow=True, is_active=True,
        )
        db.add_all([ar, income, cash]); db.commit()
        posted = fine_api.post_fine(
            assoc.id, case.id,
            HOAFinePostIn(
                property_id=prop.id, posting_on=date.today(),
                receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
            ), db=db, current_user=admin,
        )
        assert posted.amount_paid == Decimal("0.00")
        before_gl = db.query(GLTransaction).count()
        response = Response()
        options = fine_payments.fine_cash_options(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=owner,
        )
        assert response.headers["cache-control"] == "no-store"
        assert [x.id for x in options] == [cash.id]
        first = fine_payments.record_fine_payment(
            assoc.id, case.id, _fine_receipt(prop, tenant, cash),
            db=db, current_user=owner,
        )
        assert first.status == "POSTED" and first.manually_recorded
        assert first.bank_collection_executed is False
        assert db.get(HOAViolationFine, posted.id).amount_paid == Decimal("10.00")
        receipt = db.get(Receipt, first.receipt_id)
        assert receipt.type == "HOA_FINE"
        assert receipt.owner_id is None and receipt.tenant_user_id is None
        assert db.query(ReceiptLine).filter(ReceiptLine.receipt_id == receipt.id).count() == 1
        transaction = db.get(GLTransaction, receipt.gl_transaction_id)
        assert transaction.source_type == "receipt" and transaction.source_id == receipt.id
        entries = db.query(GLEntry).filter(GLEntry.transaction_id == transaction.id).all()
        assert len(entries) == 2
        assert any(e.gl_account_id == cash.id and e.debit == Decimal("10.00") for e in entries)
        assert any(e.gl_account_id == ar.id and e.credit == Decimal("10.00") for e in entries)
        replay = fine_payments.record_fine_payment(
            assoc.id, case.id, _fine_receipt(prop, tenant, cash),
            db=db, current_user=admin,
        )
        assert replay.id == first.id and db.query(GLTransaction).count() == before_gl + 1
        with pytest.raises(HTTPException) as conflict:
            fine_payments.record_fine_payment(
                assoc.id, case.id, _fine_receipt(prop, tenant, cash, reference="OTHER"),
                db=db, current_user=admin,
            )
        assert conflict.value.status_code == 409
        with pytest.raises(HTTPException) as too_much:
            fine_payments.record_fine_payment(
                assoc.id, case.id,
                _fine_receipt(prop, tenant, cash, key="hoa-fine-receipt-00002",
                              amount="25.00"),
                db=db, current_user=admin,
            )
        assert too_much.value.status_code == 409
        with pytest.raises(PostingError):
            reverse_receipt(
                db, original=receipt, reversal_date=date.today(),
                memo="Attempt generic reversal", created_by=admin,
            )
        with pytest.raises(PostingError):
            process_nsf_receipt(
                db, original=receipt, process_date=date.today(),
                memo="Attempt generic NSF", created_by=admin,
            )
        with pytest.raises(ValidationError):
            ReceiptCreateIn(
                type="HOA_FINE", receipt_date=date.today(), amount=Decimal("1.00"),
                cash_gl_account_id=cash.id,
            )
        second = fine_payments.record_fine_payment(
            assoc.id, case.id,
            _fine_receipt(prop, tenant, cash, key="hoa-fine-receipt-00002",
                          amount="15.00", reference="FINE-CHECK-101"),
            db=db, current_user=admin,
        )
        assert db.get(HOAViolationFine, posted.id).amount_paid == Decimal("25.00")
        with pytest.raises(HTTPException) as paid:
            fine_api.reverse_fine(
                assoc.id, case.id,
                HOAFineReverseIn(
                    property_id=prop.id, reversal_on=date.today(),
                    reason="Cannot reverse while allocated funds remain",
                ), db=db, current_user=admin,
            )
        assert paid.value.status_code == 409
        reversed_second = fine_payments.reverse_fine_payment(
            assoc.id, case.id, second.id, _fine_receipt_reversal(prop),
            db=db, current_user=owner,
        )
        assert reversed_second.status == "REVERSED"
        assert reversed_second.reversal_receipt_id != second.receipt_id
        assert db.get(HOAViolationFine, posted.id).amount_paid == Decimal("10.00")
        with pytest.raises(HTTPException) as duplicate:
            fine_payments.reverse_fine_payment(
                assoc.id, case.id, second.id, _fine_receipt_reversal(prop),
                db=db, current_user=admin,
            )
        assert duplicate.value.status_code == 409
        fine_payments.reverse_fine_payment(
            assoc.id, case.id, first.id, _fine_receipt_reversal(prop),
            db=db, current_user=admin,
        )
        assert db.get(HOAViolationFine, posted.id).amount_paid == Decimal("0.00")
        history_response = Response()
        history = fine_payments.list_fine_payments(
            assoc.id, case.id, history_response, property_id=prop.id,
            db=db, current_user=admin,
        )
        assert history_response.headers["cache-control"] == "no-store"
        assert len(history) == 2 and all(p.status == "REVERSED" for p in history)
        assert db.query(GLTransaction).count() == before_gl + 4
        assert db.query(Receipt).count() == 4
        assert db.query(Charge).count() == db.query(RentInvoice).count() == 0
        with pytest.raises(HTTPException):
            _model_for_table("hoa_violation_fine_payments")
        reversed_fine = fine_api.reverse_fine(
            assoc.id, case.id,
            HOAFineReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Fine reversal after both receipts cancelled",
            ), db=db, current_user=admin,
        )
        assert reversed_fine.status == "REVERSED"
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_fine_receipt_member_scope_period_lock_deposit_and_revocation(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop, other, outside = props
        fine_api.decide_fine(
            assoc.id, case.id, _fine_decision(prop, tenant),
            db=db, current_user=admin,
        )
        ar = GLAccount(
            organization_id=admin.organization_id, gl_number="FINE-LOCK-AR",
            name="Locked fine receivable", account_type="ASSET", is_active=True,
        )
        income = GLAccount(
            organization_id=admin.organization_id, gl_number="FINE-LOCK-INCOME",
            name="Locked fine income", account_type="INCOME", is_active=True,
        )
        cash = GLAccount(
            organization_id=admin.organization_id, gl_number="FINE-LOCK-CASH",
            name="Recorded fine cash", account_type="ASSET",
            include_on_cash_flow=True, is_active=True,
        )
        db.add_all([ar, income, cash]); db.commit()
        fine_api.post_fine(
            assoc.id, case.id,
            HOAFinePostIn(
                property_id=prop.id, posting_on=date.today(),
                receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
            ), db=db, current_user=admin,
        )
        payload = _fine_receipt(prop, tenant, cash)
        for actor, prop_id, member_id in (
            (manager, prop.id, tenant.id),
            (tenant, prop.id, tenant.id),
            (foreign, prop.id, tenant.id),
            (admin, other.id, tenant.id),
            (admin, outside.id, tenant.id),
            (admin, prop.id, admin.id),
        ):
            with pytest.raises(HTTPException):
                fine_payments.record_fine_payment(
                    assoc.id, case.id,
                    payload.model_copy(update={"property_id": prop_id, "member_user_id": member_id}),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            fine_payments.record_fine_payment(
                assoc.id, case.id,
                payload.model_copy(update={"cash_gl_account_id": ar.id}),
                db=db, current_user=admin,
            )
        org = db.get(Organization, admin.organization_id)
        org.locked_through_date = date.today(); db.flush()
        with pytest.raises(HTTPException) as locked:
            fine_payments.record_fine_payment(
                assoc.id, case.id, payload, db=db, current_user=admin,
            )
        assert locked.value.status_code == 409
        assert db.query(Receipt).count() == 0
        org.locked_through_date = None; db.flush()
        actual = fine_payments.record_fine_payment(
            assoc.id, case.id, payload, db=db, current_user=admin,
        )
        org.locked_through_date = date.today(); db.flush()
        with pytest.raises(HTTPException) as reversal_locked:
            fine_payments.reverse_fine_payment(
                assoc.id, case.id, actual.id, _fine_receipt_reversal(prop),
                db=db, current_user=admin,
            )
        assert reversal_locked.value.status_code == 409
        org.locked_through_date = None; db.flush()
        assert db.query(HOAViolationFinePayment).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_fine_payment",
        ).count() == 1
    finally:
        db.rollback(); db.close(); engine.dispose()


def _appeal_payload(prop, key="hoa-fine-appeal-request-0001", **changes):
    values = dict(property_id=prop.id, received_on=date.today(),
                  appeal_reason="Member disputed synthetic board fine",
                  request_key=key)
    values.update(changes)
    return HOAFineAppealIn(**values)


def _appeal_decision(prop, outcome="UPHELD", key="hoa-fine-appeal-decision-0001", **changes):
    values = dict(property_id=prop.id, result=outcome,
                  decision_note="Association board reviewed member appeal",
                  request_key=key)
    values.update(changes)
    return HOAFineAppealDecisionIn(**values)


def test_fine_appeal_board_disposition_holds_posting_and_preserves_finance(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        fine = fine_api.decide_fine(
            assoc.id, case.id, _fine_decision(prop, tenant),
            db=db, current_user=admin,
        )
        before = _balances(db)
        response = Response()
        assert appeals_api.list_appeals(
            assoc.id, case.id, response, property_id=prop.id,
            db=db, current_user=admin,
        ) == []
        assert response.headers["cache-control"] == "no-store"
        opened = appeals_api.record_appeal(
            assoc.id, case.id, _appeal_payload(prop),
            db=db, current_user=owner,
        )
        assert opened.status == "OPEN" and opened.member_user_id == tenant.id
        assert not opened.accounting_reversal_pending
        assert appeals_api.record_appeal(
            assoc.id, case.id, _appeal_payload(prop),
            db=db, current_user=owner,
        ).id == opened.id
        with pytest.raises(HTTPException) as changed_key:
            appeals_api.record_appeal(
                assoc.id, case.id, _appeal_payload(
                    prop, appeal_reason="Changed reason using same key",
                ), db=db, current_user=admin,
            )
        assert changed_key.value.status_code == 409
        with pytest.raises(HTTPException) as duplicate_open:
            appeals_api.record_appeal(
                assoc.id, case.id, _appeal_payload(
                    prop, key="hoa-fine-appeal-request-0002",
                ), db=db, current_user=admin,
            )
        assert duplicate_open.value.status_code == 409
        ar = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-APPEAL-AR",
            name="Fine receivable", account_type="ASSET", is_active=True,
        )
        income = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-APPEAL-INCOME",
            name="Fine income", account_type="INCOME", is_active=True,
        )
        cash = GLAccount(
            organization_id=admin.organization_id, gl_number="HOA-APPEAL-CASH",
            name="Fine cash", account_type="ASSET", is_active=True,
            include_on_cash_flow=True,
        )
        db.add_all([ar, income, cash]); db.commit()
        posting = HOAFinePostIn(
            property_id=prop.id, posting_on=date.today(),
            receivable_gl_account_id=ar.id, income_gl_account_id=income.id,
        )
        with pytest.raises(HTTPException) as held:
            fine_api.post_fine(
                assoc.id, case.id, posting, db=db, current_user=owner,
            )
        assert held.value.status_code == 409
        assert _balances(db) == before
        upheld = appeals_api.decide_appeal(
            assoc.id, case.id, opened.id, _appeal_decision(prop),
            db=db, current_user=admin,
        )
        assert upheld.status == "UPHELD" and upheld.decision_board_seat_id == seat.id
        assert appeals_api.decide_appeal(
            assoc.id, case.id, opened.id, _appeal_decision(prop),
            db=db, current_user=admin,
        ).id == opened.id
        fine_api.post_fine(
            assoc.id, case.id, posting, db=db, current_user=owner,
        )
        assert db.query(GLTransaction).count() == before[1] + 1
        second = appeals_api.record_appeal(
            assoc.id, case.id,
            _appeal_payload(prop, key="hoa-fine-appeal-request-0003"),
            db=db, current_user=owner,
        )
        with pytest.raises(HTTPException):
            fine_payments.record_fine_payment(
                assoc.id, case.id, _fine_receipt(prop, tenant, cash),
                db=db, current_user=owner,
            )
        vacated = appeals_api.decide_appeal(
            assoc.id, case.id, second.id,
            _appeal_decision(prop, outcome="VACATED",
                             key="hoa-fine-appeal-decision-0002"),
            db=db, current_user=admin,
        )
        assert vacated.accounting_reversal_pending
        assert vacated.status == "VACATED"
        with pytest.raises(HTTPException):
            fine_payments.record_fine_payment(
                assoc.id, case.id, _fine_receipt(prop, tenant, cash),
                db=db, current_user=owner,
            )
        with pytest.raises(HTTPException) as reopened:
            appeals_api.record_appeal(
                assoc.id, case.id,
                _appeal_payload(prop, key="hoa-fine-appeal-request-0004"),
                db=db, current_user=admin,
            )
        assert reopened.value.status_code == 409
        assert db.query(Receipt).count() == 0
        assert db.query(GLTransaction).count() == before[1] + 1
        reversed_fine = fine_api.reverse_fine(
            assoc.id, case.id, HOAFineReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Board vacated the recorded fine on appeal",
            ), db=db, current_user=owner,
        )
        assert reversed_fine.status == "REVERSED"
        history = appeals_api.list_appeals(
            assoc.id, case.id, Response(), property_id=prop.id,
            db=db, current_user=admin,
        )
        assert [item.status for item in history] == ["UPHELD", "VACATED"]
        assert history[-1].accounting_reversal_pending is False
        assert db.query(GLTransaction).count() == before[1] + 2
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_violation_fine_appeal",
        ).order_by(AuditLog.id).all()
        assert len(audit) == 4
        assert all("Member disputed synthetic" not in str(a.new_value) for a in audit)
        assert all("Association board reviewed" not in str(a.new_value) for a in audit)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_violation_fine_appeals")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_fine_appeals_scope_evidence_and_board_authorization(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop, other, outside = props
        fine_api.decide_fine(
            assoc.id, case.id, _fine_decision(prop, tenant),
            db=db, current_user=admin,
        )
        for actor, property_id in (
            (manager, prop.id), (tenant, prop.id),
            (foreign, prop.id), (admin, outside.id),
            (manager, other.id),
        ):
            with pytest.raises(HTTPException):
                appeals_api.record_appeal(
                    assoc.id, case.id, _appeal_payload(prop, property_id=property_id),
                    db=db, current_user=actor,
                )
            with pytest.raises(HTTPException):
                appeals_api.list_appeals(
                    assoc.id, case.id, Response(), property_id=property_id,
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as false_proof:
            appeals_api.record_appeal(
                assoc.id, case.id, _appeal_payload(
                    prop, supporting_attachment_id=999999,
                ), db=db, current_user=owner,
            )
        assert false_proof.value.status_code == 409
        opened = appeals_api.record_appeal(
            assoc.id, case.id,
            _appeal_payload(prop, supporting_attachment_id=proof.id),
            db=db, current_user=owner,
        )
        assert opened.supporting_attachment_id == proof.id
        with pytest.raises(HTTPException) as unassigned_board:
            appeals_api.decide_appeal(
                assoc.id, case.id, opened.id, _appeal_decision(prop),
                db=db, current_user=manager,
            )
        assert unassigned_board.value.status_code == 403
        with pytest.raises(HTTPException):
            appeals_api.decide_appeal(
                assoc.id, case.id, opened.id,
                _appeal_decision(prop, property_id=other.id),
                db=db, current_user=admin,
            )
        result = appeals_api.decide_appeal(
            assoc.id, case.id, opened.id, _appeal_decision(prop),
            db=db, current_user=admin,
        )
        assert result.status == "UPHELD"
        with pytest.raises(HTTPException) as immutable:
            appeals_api.decide_appeal(
                assoc.id, case.id, opened.id,
                _appeal_decision(prop, outcome="VACATED"),
                db=db, current_user=admin,
            )
        assert immutable.value.status_code == 409
        assert db.query(HOAFineAppeal).count() == 1
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_board_portal_only_lists_currently_authorized_pending_fine_appeals(monkeypatch):
    db, engine = _db()
    try:
        monkeypatch.setattr(member_api, "permission_allows_user", lambda *a, **kw: True)
        def board_gates(*args, **kwargs):
            return [SimpleNamespace(key=k, release_allowed=True,
                                    entitlement_allowed=True, org_config_allowed=True)
                    for k in arc_board.HOA_GATES]
        monkeypatch.setattr(board_portal, "resolve_customer_features", board_gates)
        users, props, assoc, case, draft, seat, proof = _record_served_fine_case(db, monkeypatch)
        admin, owner, manager, tenant, foreign = users
        prop = props[0]
        fine = fine_api.decide_fine(
            assoc.id, case.id, _fine_decision(prop, tenant),
            db=db, current_user=admin,
        )
        appeal = appeals_api.record_appeal(
            assoc.id, case.id, _appeal_payload(prop),
            db=db, current_user=owner,
        )
        response = Response()
        rows = board_portal.my_board_fine_appeals(response, db=db, current_user=admin)
        assert response.headers["cache-control"] == "no-store"
        assert len(rows) == 1
        row = rows[0]
        assert row.appeal_id == appeal.id and row.fine_id == fine.id
        assert row.association_id == assoc.id and row.property_id == prop.id
        assert row.case_id == case.id and row.member_user_id == tenant.id
        assert row.status == "OPEN"
        for actor in (manager, tenant, foreign):
            # Verified non-board accounts get an empty board workspace;
            # other invalid accounts may be rejected. Neither may see
            # another member's private pending appeal.
            try:
                denied = board_portal.my_board_fine_appeals(
                    Response(), db=db, current_user=actor,
                )
            except HTTPException as exc:
                assert exc.status_code in {403, 404}
            else:
                assert denied == []
        db.get(HOABoardSeat, seat.id).decision_authorized = False
        db.flush()
        assert board_portal.my_board_fine_appeals(
            Response(), db=db, current_user=admin,
        ) == []
        db.get(HOABoardSeat, seat.id).decision_authorized = True
        db.flush()
        assert len(board_portal.my_board_fine_appeals(
            Response(), db=db, current_user=admin,
        )) == 1
        monkeypatch.setattr(board_portal, "resolve_customer_features",
                            lambda *a, **kw: [])
        with pytest.raises(HTTPException) as disabled:
            board_portal.my_board_fine_appeals(
                Response(), db=db, current_user=admin,
            )
        assert disabled.value.status_code == 404
        monkeypatch.setattr(board_portal, "resolve_customer_features", board_gates)
        decision = appeals_api.decide_appeal(
            assoc.id, case.id, appeal.id, _appeal_decision(prop),
            db=db, current_user=admin,
        )
        assert decision.status == "UPHELD"
        assert board_portal.my_board_fine_appeals(
            Response(), db=db, current_user=admin,
        ) == []
        assert _balances(db) == (0, 0, 0, 0)
    finally:
        db.rollback(); db.close(); engine.dispose()
