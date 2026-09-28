"""Draft HOA planning is isolated; it never creates a payable, charge or posted GL."""
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
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_assessments as api
from app.routers import hoa_associations as hoa
from app.schemas.hoa_assessment import HOAAssessmentProposalIn
from app.schemas.hoa_association import HOAAssociationIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def access(monkeypatch):
    # _scope delegates authorization to hoa_associations; patch the owner of
    # those dependency symbols, not the assessment router that imports _access.
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True)
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="HOA Drafts", slug="hoa-drafts")
    other = Organization(name="HOA Drafts Other", slug="hoa-drafts-other")
    db.add_all([org, other])
    db.flush()
    users = []
    for o, role, email in ((org, UserRole.ADMIN, "admin"),
                            (org, UserRole.OWNER, "owner"),
                            (org, UserRole.MANAGER, "manager"),
                            (org, UserRole.TENANT, "tenant"),
                            (other, UserRole.ADMIN, "foreign")):
        person = User(organization_id=o.id, role=role,
                      email=f"hoa-draft-{email}@example.test",
                      first_name=email, last_name="Drafts",
                      hashed_password="x", is_active=True)
        db.add(person)
        users.append(person)
    db.flush()
    props = []
    for o, name in ((org, "Assigned"), (org, "Unassigned"), (other, "Foreign")):
        p = Property(organization_id=o.id, name=name, address_line1="100 Test",
                     city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(p)
        props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id,
                              user_id=users[2].id, role=UserRole.MANAGER,
                              is_active=True))
    db.commit()
    association = hoa.create_association(HOAAssociationIn(
        name="Recorded HOA", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0])
    return users, props, association


def _payload(property_id, **changes):
    values = dict(
        property_id=property_id, title="Proposed common area budget",
        assessment_type="RECURRING", frequency="QUARTERLY",
        proposed_amount="125.50", proposed_first_on=date(2027, 1, 1),
        proposed_through=None,
    )
    values.update(changes)
    return HOAAssessmentProposalIn(**values)


def test_recurring_special_drafts_crud_and_no_postings():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        first = api.create_proposal(association.id, _payload(assigned.id),
                                    db=db, current_user=admin)
        special = api.create_proposal(association.id, _payload(
            assigned.id, title="Proposed roof reserve", assessment_type="SPECIAL",
            frequency="ONE_TIME", proposed_amount="500"),
            db=db, current_user=owner)
        assert first.status == special.status == "DRAFT"
        assert first.proposed_amount == Decimal("125.50")
        assert special.proposed_amount == Decimal("500")
        assert len(api.list_proposals(association.id, Response(), assigned.id,
                                      db=db, current_user=manager)) == 2
        changed = api.update_proposal(association.id, first.id,
                                      _payload(assigned.id, proposed_amount="150"),
                                      db=db, current_user=admin)
        assert changed.proposed_amount == Decimal("150")
        api.archive_proposal(association.id, first.id, assigned.id, db=db, current_user=owner)
        assert [x.id for x in api.list_proposals(association.id, Response(), assigned.id,
                                                db=db, current_user=admin)] == [special.id]
        assert db.query(HOAAssessmentProposal).count() == 2
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_assessment_proposal").count() == 4
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.close(); engine.dispose()


def test_scope_cross_org_manager_and_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        proposal = api.create_proposal(association.id, _payload(assigned.id),
                                       db=db, current_user=admin)
        for actor, prop in ((manager, unassigned), (foreign, assigned), (manager, other)):
            with pytest.raises(HTTPException) as exc:
                api.list_proposals(association.id, Response(), prop.id,
                                   db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_proposal(association.id, _payload(assigned.id),
                                    db=db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.create_proposal(association.id, _payload(other.id),
                                db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.update_proposal(association.id, proposal.id, _payload(unassigned.id),
                                db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            api.list_proposals(association.id, Response(), assigned.id,
                               db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=False)
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_proposals(association.id, Response(), assigned.id,
                               db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_schema_fails_closed_for_actual_charge_or_approval_fields():
    for changes in (
        {"proposed_amount": "-1"},
        {"proposed_amount": "0"},
        {"proposed_amount": "1.001"},
        {"frequency": "DAILY"},
        {"assessment_type": "SPECIAL", "frequency": "MONTHLY"},
        {"assessment_type": "RECURRING", "frequency": "ONE_TIME"},
        {"proposed_through": date(2026, 1, 1)},
        {"status": "APPROVED"},
        {"tenant_user_id": 12},
        {"gl_account_id": 1},
    ):
        with pytest.raises(ValidationError):
            _payload(1, **changes)


def test_association_unlink_prevents_draft_read_or_write():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        first = api.create_proposal(association.id, _payload(assigned.id),
                                    db=db, current_user=admin)
        hoa.update_association(association.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[unassigned.id]),
            db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.list_proposals(association.id, Response(), assigned.id, db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.archive_proposal(association.id, first.id, assigned.id, db=db, current_user=admin)
        assert exc.value.status_code == 404
        # Relinking cannot silently resurrect old staff assumptions.
        hoa.update_association(association.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[assigned.id, unassigned.id]),
            db=db, current_user=admin)
        assert api.list_proposals(association.id, Response(), assigned.id,
                                  db=db, current_user=admin) == []
        assert db.query(HOAAssessmentProposal).filter_by(id=first.id).one().is_active is False
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_assessment_proposals")
        assert exc.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_draft_list_not_cached_or_implicitly_approved():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        created = api.create_proposal(
            association.id, _payload(assigned.id), db=db, current_user=admin)
        response = Response()
        result = api.list_proposals(
            association.id, response, assigned.id, db=db, current_user=manager)
        assert response.headers["cache-control"] == "no-store"
        assert len(result) == 1
        assert result[0].id == created.id
        assert result[0].status == "DRAFT"
        data = result[0].model_dump()
        for prohibited in ("payer", "due_on", "approved", "gl_transaction_id", "tenant_id", "charge_id"):
            assert prohibited not in data
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.close(); engine.dispose()



def test_association_archive_retains_no_active_draft_or_financial_effect():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        first = api.create_proposal(association.id, _payload(assigned.id),
                                    db=db, current_user=admin)
        second = api.create_proposal(association.id, _payload(unassigned.id),
                                     db=db, current_user=owner)
        hoa.archive_association(association.id, db=db, current_user=admin)
        assert db.query(HOAAssessmentProposal).filter(
            HOAAssessmentProposal.association_id == association.id,
            HOAAssessmentProposal.is_active.is_(True),
        ).count() == 0
        for prop in (assigned, unassigned):
            with pytest.raises(HTTPException) as exc:
                api.list_proposals(association.id, Response(), prop.id,
                                   db=db, current_user=admin)
            assert exc.value.status_code == 404
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_assessment_proposal",
            AuditLog.action == "association_archived",
        ).count() == 2
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
