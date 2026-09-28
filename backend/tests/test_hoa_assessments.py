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
from app.models.gl_account import GLAccount
from app.routers import hoa_issuance_readiness as readiness_api
from app.models.gl_transaction import GLTransaction
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.hoa_payer_draft import HOAPayerDraft
from app.models.hoa_planned_occurrence import HOAPlannedOccurrence
from app.routers import hoa_planned_occurrences as plan_api
from app.schemas.hoa_planned_occurrence import HOAPlanGenerationIn
from app.models.contact import Contact
from app.routers import hoa_payer_drafts as payer_api
from app.schemas.hoa_payer_draft import HOAPayerDraftIn
from app.schemas.hoa_association import HOAContactLinkIn
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
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
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


def test_calendar_preview_keeps_month_end_anchor_without_issuing_charges():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, _, _), association = _seed(db)
        proposal = api.create_proposal(association.id, _payload(
            assigned.id, frequency="MONTHLY", proposed_first_on=date(2028, 1, 31),
            proposed_amount="125.50",
        ), db=db, current_user=admin)
        result = api.preview_proposal(
            association.id, proposal.id, Response(),
            property_id=assigned.id, date_from=date(2028, 1, 1),
            date_to=date(2028, 4, 30), db=db, current_user=manager,
        )
        assert [r.proposed_on for r in result.occurrences] == [
            date(2028, 1, 31), date(2028, 2, 29),
            date(2028, 3, 31), date(2028, 4, 30),
        ]
        assert result.proposed_total == Decimal("502.00")
        assert result.status == "UNISSUED_PREVIEW"
        assert result.issuance_enabled is False
        assert all(x.status == "DRAFT_ONLY" for x in result.occurrences)
        assert "due_on" not in result.model_dump()
        assert "payer_id" not in result.model_dump()
        assert db.query(Charge).count() == db.query(GLTransaction).count() == db.query(Lease).count() == 0
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_assessment_proposal").count() == 1
    finally:
        db.close()
        engine.dispose()


def test_calendar_preview_quarterly_annual_special_bounds_and_far_past():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, _, _), association = _seed(db)
        quarter = api.create_proposal(association.id, _payload(
            assigned.id, frequency="QUARTERLY",
            proposed_first_on=date(2026, 11, 30),
            proposed_through=date(2031, 12, 31),
        ), db=db, current_user=admin)
        result = api.preview_proposal(
            association.id, quarter.id, Response(),
            property_id=assigned.id, date_from=date(2030, 1, 1),
            date_to=date(2030, 12, 31), db=db, current_user=owner,
        )
        assert [x.proposed_on for x in result.occurrences] == [
            date(2030, 2, 28), date(2030, 5, 31),
            date(2030, 8, 31), date(2030, 11, 30),
        ]
        annual = api.create_proposal(association.id, _payload(
            assigned.id, frequency="ANNUAL",
            proposed_first_on=date(2028, 2, 29),
        ), db=db, current_user=admin)
        result = api.preview_proposal(
            association.id, annual.id, Response(),
            property_id=assigned.id, date_from=date(2030, 1, 1),
            date_to=date(2032, 12, 31), db=db, current_user=admin,
        )
        assert [x.proposed_on for x in result.occurrences] == [
            date(2030, 2, 28), date(2031, 2, 28), date(2032, 2, 29),
        ]
        special = api.create_proposal(association.id, _payload(
            assigned.id, frequency="ONE_TIME", assessment_type="SPECIAL",
            proposed_first_on=date(2028, 6, 12),
        ), db=db, current_user=admin)
        result = api.preview_proposal(
            association.id, special.id, Response(),
            property_id=assigned.id, date_from=date(2029, 1, 1),
            date_to=date(2029, 12, 31), db=db, current_user=admin,
        )
        assert result.occurrences == [] and result.proposed_total == Decimal("0.00")
        for start, end in ((date(2030, 1, 2), date(2030, 1, 1)),
                           (date(2028, 1, 1), date(2035, 1, 1))):
            with pytest.raises(HTTPException) as exc:
                api.preview_proposal(
                    association.id, quarter.id, Response(),
                    property_id=assigned.id, date_from=start, date_to=end,
                    db=db, current_user=admin,
                )
            assert exc.value.status_code == 422
    finally:
        db.close()
        engine.dispose()


def test_calendar_preview_authorization_and_archive_fail_closed(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        proposal = api.create_proposal(
            association.id, _payload(assigned.id),
            db=db, current_user=admin,
        )
        def preview(actor, prop_id=assigned.id):
            return api.preview_proposal(
                association.id, proposal.id, Response(),
                property_id=prop_id, date_from=date(2027, 1, 1),
                date_to=date(2027, 12, 31), db=db, current_user=actor,
            )
        for actor, pid in ((tenant, assigned.id), (foreign, assigned.id),
                           (manager, unassigned.id), (admin, other.id)):
            with pytest.raises(HTTPException):
                preview(actor, pid)
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            preview(admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as exc:
            preview(admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
        ])
        api.archive_proposal(association.id, proposal.id, assigned.id,
                             db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            preview(admin)
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_suggested_payer_lifecycle_is_not_legal_liability_or_charge():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        local = Contact(organization_id=admin.organization_id, display_name="Staff contact",
                        contact_type="PERSON", is_active=True)
        db.add(local); db.commit()
        linked = hoa.add_contact_link(
            association.id, HOAContactLinkIn(
                property_id=assigned.id, contact_id=local.id,
            ), db=db, current_user=admin,
        )
        proposal = api.create_proposal(association.id, _payload(assigned.id),
                                       db=db, current_user=admin)
        suggested = payer_api.set_payer_draft(
            association.id, proposal.id, HOAPayerDraftIn(
                property_id=assigned.id, contact_link_id=linked.id,
            ), db=db, current_user=owner,
        )
        assert suggested.status == "STAFF_SUGGESTED_UNVERIFIED"
        assert suggested.legal_payer_verified is False
        assert suggested.issue_charge_enabled is False
        assert suggested.contact_name == "Staff contact"
        response = Response()
        assert payer_api.get_payer_draft(
            association.id, proposal.id, response, assigned.id,
            db=db, current_user=manager,
        ).id == suggested.id
        assert response.headers["cache-control"] == "no-store"
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        payer_api.archive_payer_draft(
            association.id, proposal.id, assigned.id,
            db=db, current_user=admin,
        )
        assert payer_api.get_payer_draft(
            association.id, proposal.id, Response(), assigned.id,
            db=db, current_user=manager,
        ) is None
        with pytest.raises(HTTPException) as exc:
            payer_api.set_payer_draft(
                association.id, proposal.id, HOAPayerDraftIn(
                    property_id=assigned.id, contact_link_id=linked.id,
                ), db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(HOAPayerDraft).count() == 1
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_payer_draft",
        ).count() == 2
    finally:
        db.close(); engine.dispose()


def test_suggested_payer_cross_scope_and_relink_guards(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        local = Contact(organization_id=admin.organization_id, display_name="Local",
                        contact_type="PERSON", is_active=True)
        db.add(local); db.commit()
        assigned_link = hoa.add_contact_link(
            association.id, HOAContactLinkIn(
                property_id=assigned.id, contact_id=local.id,
            ), db=db, current_user=admin,
        )
        other_link = hoa.add_contact_link(
            association.id, HOAContactLinkIn(
                property_id=unassigned.id, contact_id=local.id,
            ), db=db, current_user=admin,
        )
        proposal = api.create_proposal(association.id, _payload(assigned.id),
                                       db=db, current_user=admin)
        for actor, pid in ((manager, unassigned.id), (tenant, assigned.id),
                           (foreign, assigned.id), (admin, other.id)):
            with pytest.raises(HTTPException):
                payer_api.get_payer_draft(
                    association.id, proposal.id, Response(), pid,
                    db=db, current_user=actor,
                )
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                payer_api.set_payer_draft(
                    association.id, proposal.id, HOAPayerDraftIn(
                        property_id=assigned.id, contact_link_id=assigned_link.id,
                    ), db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as exc:
            payer_api.set_payer_draft(
                association.id, proposal.id, HOAPayerDraftIn(
                    property_id=assigned.id, contact_link_id=other_link.id,
                ), db=db, current_user=owner,
            )
        assert exc.value.status_code == 404
        for forbidden in ("legal_payer_verified", "tenant_user_id", "gl_account_id",
                          "issue_charge_enabled", "is_owner"):
            with pytest.raises(ValidationError):
                HOAPayerDraftIn(
                    property_id=assigned.id, contact_link_id=assigned_link.id,
                    **{forbidden: True},
                )
        with pytest.raises(HTTPException):
            _model_for_table("hoa_payer_drafts")
        record = payer_api.set_payer_draft(
            association.id, proposal.id, HOAPayerDraftIn(
                property_id=assigned.id, contact_link_id=assigned_link.id,
            ), db=db, current_user=admin,
        )
        hoa.remove_contact_link(
            association.id, assigned_link.id, assigned.id,
            db=db, current_user=admin,
        )
        assert payer_api.get_payer_draft(
            association.id, proposal.id, Response(), assigned.id,
            db=db, current_user=admin,
        ) is None
        assert db.get(HOAPayerDraft, record.id).is_active is False
        hoa.add_contact_link(
            association.id, HOAContactLinkIn(
                property_id=assigned.id, contact_id=local.id,
            ), db=db, current_user=admin,
        )
        assert payer_api.get_payer_draft(
            association.id, proposal.id, Response(), assigned.id,
            db=db, current_user=admin,
        ) is None
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close(); engine.dispose()


def test_suggested_payer_feature_revocation_and_proposal_archive(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), association = _seed(db)
        local = Contact(organization_id=admin.organization_id, display_name="Test",
                        contact_type="PERSON", is_active=True)
        db.add(local); db.commit()
        link = hoa.add_contact_link(
            association.id, HOAContactLinkIn(property_id=assigned.id, contact_id=local.id),
            db=db, current_user=admin,
        )
        proposal = api.create_proposal(
            association.id, _payload(assigned.id), db=db, current_user=admin,
        )
        record = payer_api.set_payer_draft(
            association.id, proposal.id, HOAPayerDraftIn(
                property_id=assigned.id, contact_link_id=link.id,
            ), db=db, current_user=admin,
        )
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            payer_api.get_payer_draft(
                association.id, proposal.id, Response(), assigned.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as exc:
            payer_api.get_payer_draft(
                association.id, proposal.id, Response(), assigned.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
        ])
        api.archive_proposal(
            association.id, proposal.id, assigned.id,
            db=db, current_user=admin,
        )
        assert db.get(HOAPayerDraft, record.id).is_active is False
        with pytest.raises(HTTPException) as exc:
            payer_api.get_payer_draft(
                association.id, proposal.id, Response(), assigned.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def _plan_fixture(db):
    (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
    contact = Contact(
        organization_id=admin.organization_id, display_name="Suggested only",
        contact_type="PERSON", is_active=True,
    )
    db.add(contact)
    db.commit()
    link = hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(property_id=assigned.id, contact_id=contact.id),
        db=db, current_user=admin,
    )
    proposal = api.create_proposal(
        assoc.id, _payload(
            assigned.id, frequency="MONTHLY",
            proposed_first_on=date(2028, 1, 31), proposed_amount="125.50",
        ), db=db, current_user=admin,
    )
    payer = payer_api.set_payer_draft(
        assoc.id, proposal.id,
        HOAPayerDraftIn(property_id=assigned.id, contact_link_id=link.id),
        db=db, current_user=owner,
    )
    return (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc, proposal, payer


def _generate(db, actor, assoc, proposal, prop, start=date(2028, 1, 1),
              end=date(2028, 4, 30)):
    return plan_api.generate_occurrences(
        assoc.id, proposal.id,
        HOAPlanGenerationIn(property_id=prop.id, date_from=start, date_to=end),
        db=db, current_user=actor,
    )


def test_occurrence_generation_idempotent_snapshots_and_void_history():
    db, engine = _db()
    try:
        (admin, owner, manager, _, _), (prop, _, _), assoc, proposal, payer = _plan_fixture(db)
        first = _generate(db, admin, assoc, proposal, prop)
        assert first.new_count == 4 and first.existing_count == 0
        assert [x.proposed_on for x in first.rows] == [
            date(2028, 1, 31), date(2028, 2, 29),
            date(2028, 3, 31), date(2028, 4, 30),
        ]
        assert all(
            not row.is_issued and not row.is_receivable
            and not row.legal_payer_verified and not row.gl_posting_enabled
            and row.payer_draft_id == payer.id and row.proposed_amount == Decimal("125.50")
            for row in first.rows
        )
        replay = _generate(db, owner, assoc, proposal, prop)
        assert replay.new_count == 0 and replay.existing_count == 4
        assert [r.id for r in replay.rows] == [r.id for r in first.rows]
        original = db.get(HOAPlannedOccurrence, first.rows[0].id)
        # Historic amount is immutable when a proposed assessment changes.
        api.update_proposal(
            assoc.id, proposal.id,
            _payload(prop.id, frequency="MONTHLY",
                     proposed_first_on=date(2028, 1, 31), proposed_amount="150"),
            db=db, current_user=admin,
        )
        rerun = _generate(db, admin, assoc, proposal, prop)
        assert rerun.new_count == 0
        assert db.get(HOAPlannedOccurrence, original.id).proposed_amount == Decimal("125.50")
        added = _generate(
            db, admin, assoc, proposal, prop,
            start=date(2028, 5, 1), end=date(2028, 5, 31),
        )
        assert added.new_count == 1 and added.rows[0].proposed_amount == Decimal("150")
        voided = plan_api.void_occurrence(
            assoc.id, proposal.id, original.id, property_id=prop.id,
            db=db, current_user=admin,
        )
        assert voided.status == "VOIDED" and voided.voided_at is not None
        with pytest.raises(HTTPException) as exc:
            plan_api.void_occurrence(
                assoc.id, proposal.id, original.id, property_id=prop.id,
                db=db, current_user=owner,
            )
        assert exc.value.status_code == 409
        after_void_replay = _generate(db, admin, assoc, proposal, prop)
        assert after_void_replay.new_count == 0
        assert after_void_replay.rows[0].status == "VOIDED"
        response = Response()
        history = plan_api.list_occurrences(
            assoc.id, proposal.id, response, property_id=prop.id,
            db=db, current_user=manager,
        )
        assert response.headers["cache-control"] == "no-store"
        assert len(history) == 5
        assert db.query(HOAPlannedOccurrence).count() == 5
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_planned_occurrence",
        ).count() == 6
        assert db.query(Charge).count() == db.query(GLTransaction).count() == db.query(Lease).count() == 0
        with pytest.raises(HTTPException):
            _model_for_table("hoa_planned_occurrences")
    finally:
        db.close()
        engine.dispose()


def test_occurrence_generation_scope_revocation_and_missing_payer(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, proposal, payer = _plan_fixture(db)
        for actor, property_ in (
            (manager, prop), (tenant, prop), (foreign, prop),
            (admin, outside),
        ):
            with pytest.raises(HTTPException):
                _generate(db, actor, assoc, proposal, property_)
        with pytest.raises(HTTPException):
            plan_api.list_occurrences(
                assoc.id, proposal.id, Response(), property_id=other.id,
                db=db, current_user=manager,
            )
        for actor in (tenant, foreign):
            with pytest.raises(HTTPException):
                plan_api.list_occurrences(
                    assoc.id, proposal.id, Response(), property_id=prop.id,
                    db=db, current_user=actor,
                )
        with pytest.raises(ValidationError):
            HOAPlanGenerationIn(property_id=prop.id, date_from=date(2028, 1, 1),
                                date_to=date(2028, 2, 1), charge_date=date(2028, 2, 1))
        with pytest.raises(ValidationError):
            HOAPlanGenerationIn(property_id=prop.id, date_from=date(2028, 3, 1),
                                date_to=date(2028, 2, 1))
        with pytest.raises(HTTPException) as exc:
            _generate(db, admin, assoc, proposal, prop,
                      start=date(2028, 1, 1), end=date(2035, 1, 1))
        assert exc.value.status_code == 422
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException):
            _generate(db, admin, assoc, proposal, prop)
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException):
            _generate(db, admin, assoc, proposal, prop)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
        ])
        payer_api.archive_payer_draft(
            assoc.id, proposal.id, prop.id, db=db, current_user=owner,
        )
        with pytest.raises(HTTPException) as exc:
            _generate(db, admin, assoc, proposal, prop)
        assert exc.value.status_code == 409
        assert db.query(HOAPlannedOccurrence).count() == 0
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_hoa_posting_readiness_reports_missing_authority_even_with_candidate_gl():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, _, _), assoc, proposal, payer = _plan_fixture(db)
        plan = _generate(db, admin, assoc, proposal, prop)
        occurrence = plan.rows[0]
        before = (
            db.query(Charge).count(), db.query(GLTransaction).count(),
            db.query(AuditLog).count(),
        )
        response = Response()
        empty = readiness_api.issuance_readiness(
            assoc.id, proposal.id, occurrence.id, response,
            property_id=prop.id, candidate_income_gl_account_id=None,
            db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert empty.status == "PLANNED"
        assert empty.governing_authority_verified is False
        assert empty.legal_payer_liability_verified is False
        assert empty.posting_enabled is False and empty.reversal_enabled is False
        assert "NO_VALID_INCOME_GL_CANDIDATE" in empty.missing_requirements
        local = GLAccount(
            organization_id=admin.organization_id, gl_number="E2E-HOA-INCOME",
            name="Synthetic candidate, not approved", account_type="INCOME",
            is_active=True,
        )
        db.add(local)
        db.commit()
        candidate = readiness_api.issuance_readiness(
            assoc.id, proposal.id, occurrence.id, Response(),
            property_id=prop.id, candidate_income_gl_account_id=local.id,
            db=db, current_user=owner,
        )
        assert candidate.candidate_income_account_valid is True
        assert candidate.approved_gl_mapping_verified is False
        assert "APPROVED_GL_MAPPING_UNAVAILABLE" in candidate.missing_requirements
        assert "GOVERNING_AUTHORITY_UNVERIFIED" in candidate.missing_requirements
        assert "LEGAL_PAYER_LIABILITY_UNVERIFIED" in candidate.missing_requirements
        assert candidate.posting_enabled is False
        org = db.get(Organization, admin.organization_id)
        org.locked_through_date = date(2028, 12, 31)
        db.flush()
        locked = readiness_api.issuance_readiness(
            assoc.id, proposal.id, occurrence.id, Response(),
            property_id=prop.id, candidate_income_gl_account_id=local.id,
            db=db, current_user=admin,
        )
        assert locked.accounting_period_unlocked is False
        assert "ACCOUNTING_PERIOD_LOCKED" in locked.missing_requirements
        org.locked_through_date = None
        db.flush()
        plan_api.void_occurrence(
            assoc.id, proposal.id, occurrence.id, prop.id,
            db=db, current_user=owner,
        )
        voided = readiness_api.issuance_readiness(
            assoc.id, proposal.id, occurrence.id, Response(),
            property_id=prop.id, candidate_income_gl_account_id=local.id,
            db=db, current_user=admin,
        )
        assert "OCCURRENCE_VOIDED" in voided.missing_requirements
        assert voided.posting_enabled is False
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        assert before[0] == 0 and before[1] == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_hoa_posting_readiness_honors_live_scope_and_accounting_permissions(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, unassigned, other), assoc, proposal, payer = _plan_fixture(db)
        row = _generate(db, admin, assoc, proposal, prop).rows[0]
        def check(actor, property_id=prop.id, gl_id=None):
            return readiness_api.issuance_readiness(
                assoc.id, proposal.id, row.id, Response(),
                property_id=property_id, candidate_income_gl_account_id=gl_id,
                db=db, current_user=actor,
            )
        for actor, prop_id in (
            (manager, prop.id), (tenant, prop.id), (foreign, prop.id),
            (admin, unassigned.id), (admin, other.id),
        ):
            with pytest.raises(HTTPException):
                check(actor, prop_id)
        monkeypatch.setattr(
            readiness_api, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.CHARGES",
        )
        with pytest.raises(HTTPException) as e:
            check(admin)
        assert e.value.status_code == 403
        monkeypatch.setattr(readiness_api, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as e:
            check(admin)
        assert e.value.status_code == 404
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
            SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
        ])
        payer_api.archive_payer_draft(
            assoc.id, proposal.id, prop.id, db=db, current_user=owner,
        )
        stale = check(admin)
        assert "PAYER_REFERENCE_STALE" in stale.missing_requirements
        assert stale.posting_enabled is False
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()
