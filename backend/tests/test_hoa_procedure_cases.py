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
from app.models.gl_transaction import GLTransaction
from app.models.hoa_procedure_policy import HOAProcedurePolicy
from app.models.hoa_violation_case import HOAViolationCase
from app.models.lease import Lease, RentInvoice
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_observations as observations
from app.routers import hoa_procedure_policies as policies
from app.routers import hoa_violation_cases as cases
from app.schemas.hoa_association import HOAAssociationIn
from app.schemas.hoa_observation import HOAObservationIn
from app.schemas.hoa_procedure_policy import HOAProcedurePolicyIn
from app.schemas.hoa_violation_case import HOAViolationCaseIn, HOAViolationAdvanceIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True)
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
