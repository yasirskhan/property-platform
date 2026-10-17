"""HOA board proposals remain scoped, unauthenticated and financially inert."""
from __future__ import annotations

from datetime import date
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
from app.models.gl_transaction import GLTransaction
from app.models.hoa_board import HOABoardRuleDraft, HOABoardSeat
from app.models.hoa_association import HOAContactLink
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa, hoa_board as api
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.schemas.hoa_board import HOABoardSeatIn, HOABoardRulesIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    local = Organization(name="Board Local", slug="board-local")
    outside = Organization(name="Board Outside", slug="board-outside")
    db.add_all([local, outside]); db.flush()
    actors = []
    for org, role, slug in (
        (local, UserRole.ADMIN, "admin"), (local, UserRole.OWNER, "owner"),
        (local, UserRole.MANAGER, "manager"), (local, UserRole.TENANT, "tenant"),
        (outside, UserRole.ADMIN, "foreign"),
    ):
        actor = User(organization_id=org.id, role=role,
                     email=f"board-{slug}@example.test",
                     first_name=slug, last_name="Test", hashed_password="x",
                     is_active=True)
        db.add(actor); actors.append(actor)
    db.flush()
    props = []
    for org, label in ((local, "Linked"), (local, "Unassigned"), (outside, "Foreign")):
        prop = Property(organization_id=org.id, name=label, address_line1="100 Main",
                        city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=actors[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    contact = Contact(organization_id=local.id, display_name="Staff-listed Director",
                      contact_type="PERSON", is_active=True)
    db.add(contact); db.commit()
    association = hoa.create_association(
        HOAAssociationIn(name="Board Inventory", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=actors[0],
    )
    link = hoa.add_contact_link(
        association.id, HOAContactLinkIn(
            property_id=props[0].id, contact_id=contact.id,
        ), db=db, current_user=actors[0],
    )
    return actors, props, association, link


def _seat(prop_id, link_id, **more):
    return HOABoardSeatIn(
        property_id=prop_id, contact_link_id=link_id,
        proposed_role="DIRECTOR", staff_voting_eligible=True, **more,
    )


def test_board_proposals_scoped_roster_and_no_effective_vote():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, unassigned, outside), assoc, link = _seed(db)
        before = (db.query(Charge).count(), db.query(GLTransaction).count())
        seat = api.record_board_seat(assoc.id, _seat(prop.id, link.id),
                                     db=db, current_user=admin)
        assert seat.status == "STAFF_PROPOSED_UNVERIFIED"
        assert seat.staff_voting_eligible is True
        assert seat.authority_verified is False and seat.vote_enabled is False
        rules = api.configure_proposed_board_rules(
            assoc.id, HOABoardRulesIn(
                property_id=prop.id, proposed_quorum_min=3, proposed_approval_min=2,
            ), db=db, current_user=owner,
        )
        assert rules.quorum_certified is False and rules.vote_enabled is False
        r = Response()
        roster = api.get_board_proposals(
            assoc.id, r, prop.id, db=db, current_user=manager,
        )
        assert r.headers["cache-control"] == "no-store"
        assert len(roster.seats) == 1 and roster.rules.proposed_quorum_min == 3
        assert roster.authority_verified is False and roster.vote_enabled is False
        with pytest.raises(HTTPException) as err:
            api.record_board_seat(assoc.id, _seat(prop.id, link.id),
                                  db=db, current_user=owner)
        assert err.value.status_code == 409
        api.archive_board_seat(assoc.id, seat.id, prop.id, db=db, current_user=admin)
        assert api.get_board_proposals(
            assoc.id, Response(), prop.id, db=db, current_user=manager,
        ).seats == []
        with pytest.raises(HTTPException) as err:
            api.record_board_seat(assoc.id, _seat(prop.id, link.id),
                                  db=db, current_user=admin)
        assert err.value.status_code == 409
        assert db.query(HOABoardSeat).count() == db.query(HOABoardRuleDraft).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type.in_(("hoa_board_seat", "hoa_board_rule_draft")),
        ).count() == 3
        assert (db.query(Charge).count(), db.query(GLTransaction).count()) == before
    finally:
        db.close(); engine.dispose()


def test_board_proposals_cross_org_contact_scope_and_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, unassigned, outside), assoc, link = _seed(db)
        for actor, property_id in ((manager, unassigned.id), (foreign, prop.id),
                                   (manager, outside.id), (tenant, prop.id)):
            with pytest.raises(HTTPException):
                api.get_board_proposals(
                    assoc.id, Response(), property_id, db=db, current_user=actor,
                )
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                api.record_board_seat(assoc.id, _seat(prop.id, link.id),
                                      db=db, current_user=actor)
        with pytest.raises(HTTPException) as err:
            api.record_board_seat(assoc.id, _seat(unassigned.id, link.id),
                                  db=db, current_user=admin)
        assert err.value.status_code == 404
        seat = api.record_board_seat(assoc.id, _seat(prop.id, link.id),
                                     db=db, current_user=admin)
        hoa.remove_contact_link(assoc.id, link.id, prop.id,
                                db=db, current_user=owner)
        assert api.get_board_proposals(
            assoc.id, Response(), prop.id, db=db, current_user=admin,
        ).seats == []
        assert db.get(HOABoardSeat, seat.id).is_active is False
        monkeypatch.setattr(hoa, "permission_allows_user",
                            lambda *a, **k: False)
        with pytest.raises(HTTPException) as err:
            api.get_board_proposals(assoc.id, Response(), prop.id,
                                    db=db, current_user=admin)
        assert err.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user",
                            lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as err:
            api.get_board_proposals(assoc.id, Response(), prop.id,
                                    db=db, current_user=admin)
        assert err.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close(); engine.dispose()


def test_board_proposal_schema_archive_unlink_and_inactive_contact():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, unassigned, outside), assoc, link = _seed(db)
        with pytest.raises(ValidationError):
            HOABoardSeatIn(property_id=prop.id, contact_link_id=link.id,
                           proposed_role="DIRECTOR", legal_voting_right=True)
        # Thresholds are independent staff proposals, not a hardcoded legal rule.
        assert HOABoardRulesIn(property_id=prop.id,
                               proposed_quorum_min=2, proposed_approval_min=3).proposed_approval_min == 3
        with pytest.raises(ValidationError):
            HOABoardRulesIn(property_id=prop.id, proposed_quorum_min=0)
        for table in ("hoa_board_seats", "hoa_board_rule_drafts"):
            with pytest.raises(HTTPException):
                _model_for_table(table)
        seat = api.record_board_seat(assoc.id, _seat(prop.id, link.id),
                                     db=db, current_user=admin)
        rules = api.configure_proposed_board_rules(
            assoc.id, HOABoardRulesIn(
                property_id=prop.id, proposed_quorum_min=3, proposed_approval_min=2,
            ), db=db, current_user=owner,
        )
        hoa.update_association(
            assoc.id, HOAAssociationIn(name="Board Inventory", property_ids=[unassigned.id]),
            db=db, current_user=admin,
        )
        assert db.get(HOABoardSeat, seat.id).is_active is False
        assert db.get(HOABoardRuleDraft, rules.id).is_active is False
        hoa.update_association(
            assoc.id, HOAAssociationIn(name="Board Inventory",
                                        property_ids=[prop.id, unassigned.id]),
            db=db, current_user=admin,
        )
        assert api.get_board_proposals(
            assoc.id, Response(), prop.id, db=db, current_user=admin,
        ).seats == []
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()
