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
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft
from app.models.hoa_violation_correspondence import HOAViolationCorrespondenceDraft
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
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.schemas.hoa_violation_recipient import HOAViolationRecipientIn
from app.routers.hoa_violation_correspondence import CorrespondenceIn
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
